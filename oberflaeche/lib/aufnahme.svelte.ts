// Aufnehmen im Browser (gemeinsamer Baustein; die App richtet ihn mit `aufnahmeEinrichten` ein).
//
// Das Mikrofon läuft über eine Audio-Weiche (AudioContext): Quelle -> Pegel, Quelle -> Rekorder, Quelle -> Mitschrift.
// So lässt sich die Quelle auch während der Aufnahme umschalten, ohne dass die Aufnahme abreißt.
// Der Rekorder liefert alle zwei Sekunden ein Stück, das sofort in den Gerätespeicher (IndexedDB) geht: eine Aufnahme
// übersteht ein Neuladen oder einen Absturz und lässt sich danach noch hochladen. Nach dem Beenden wird sie eine Datei;
// erst wenn sie in der Kellerwolke liegt, verschwindet sie vom Gerät. Transkribiert wird nur, wenn der Nutzer es will.
// Die Live-Mitschrift schneidet den Ton an Sprechpausen in Stücke (höchstens 15 s), wandelt sie in 16 kHz WAV und
// schickt sie nacheinander an den Hördienst der App (Feld "datei", Antwort {text}); der Text erscheint, während weiter
// aufgenommen wird. Ohne Hördienst gibt es keine Live-Mitschrift.
// Während der Aufnahme bleibt der Bildschirm an (soweit der Browser das erlaubt) und die App lädt nicht neu.
import { token } from "./api.svelte";
import { arbeit } from "./arbeit.svelte";

const STUECK_MS = 2000;
const PEGEL = 160;            // Verlauf des Pegels (alle 100 ms ein Wert); angezeigt wird, was in die Breite passt
const ZIEL_RATE = 16000;
const LIVE_MIN_S = 5;
const LIVE_MAX_S = 15;
const STILLE_S = 0.45;
const STILLE_PEGEL = 0.012;
// Pegel in Dezibel wie ein Aussteuerungsmesser: -60 dB ist leer, 0 dB voll; unter -50 dB gilt als still
const PEGEL_UNTEN_DB = -60;
const STILL_DB = -50;
const STILL_MELDEN_MS = 3000;

export interface AufnahmeEinrichtung {
  app: string;              // Name der App: Gerätespeicher "<app>-aufnahmen", gemerktes Mikrofon "<app>_mikrofon"
  hoeren: string | null;    // Hördienst der App für die Live-Mitschrift (Pfad unter /api/v1, etwa "/hoeren"); null: ohne
  name: string;             // Anfang vorgeschlagener Namen ("Sprachnotiz 2026-10-18 14-05")
}

let einrichtung: AufnahmeEinrichtung | null = null;

// Einmal beim Start der App, vor jeder Aufnahme.
export function aufnahmeEinrichten(e: AufnahmeEinrichtung): void {
  einrichtung = e;
  aufnahme.hoerbar = !!e.hoeren;
  aufnahme.live = aufnahme.live && aufnahme.hoerbar;
}

function eingerichtet(): AufnahmeEinrichtung {
  if (!einrichtung) throw new Error("Aufnehmen ist nicht eingerichtet (aufnahmeEinrichten fehlt)");
  return einrichtung;
}

const speicherName = () => `${eingerichtet().app}-aufnahmen`;
const geraetMerker = () => `${eingerichtet().app}_mikrofon`;

export interface Gespeichert {
  id: string;
  name: string;
  typ: string;
  beginn: number;
  dauer_ms: number;
  marker: { zeit: number; titel: string }[];
  groesse: number;
}

export interface LiveStueck {
  start: number;
  ende: number;
  text: string;
}

// Nach dem Beenden: die abgelegte Aufnahme (Kennung bei der App), bis der Nutzer entschieden hat, was damit geschieht.
export interface NachDerAufnahme {
  id: string;
  name: string;
  dauer_s: number;
  mitschrift: LiveStueck[];
}

export const aufnahme = $state({
  laeuft: false,
  pausiert: false,
  dauer_ms: 0,
  pegel: Array<number>(PEGEL).fill(0),
  marker: [] as { zeit: number; titel: string }[],
  name: "",
  fehler: "",
  geraete: [] as { id: string; name: string }[],
  geraet: "",
  hoerbar: false,           // die App hat einen Hördienst: Live-Mitschrift möglich
  live: true,
  mitschrift: [] as LiveStueck[],
  liveStand: "",
  // ob Ton ankommt: ok, still (seit Sekunden nichts vom Mikrofon) oder angehalten (der Browser hält den Ton zurück)
  signal: "ok" as "ok" | "still" | "angehalten",
  // nach dem Beenden: abgelegt, wartet auf die Entscheidung des Nutzers (die App bietet sie an)
  danach: null as null | NachDerAufnahme,
});

let rekorder: MediaRecorder | null = null;
let strom: MediaStream | null = null;
let ton: AudioContext | null = null;
let quelle: MediaStreamAudioSourceNode | null = null;
let analyse: AnalyserNode | null = null;
let ziel: MediaStreamAudioDestinationNode | null = null;
let abgriff: AudioWorkletNode | null = null;
let wachbleiben: { release(): Promise<void> } | null = null;
// jede Aufnahme hat ihren Lauf; Antworten der Live-Mitschrift aus einem früheren (etwa abgebrochenen) gehen verloren
let lauf = 0;
let aktuell: Gespeichert | null = null;
let takt: ReturnType<typeof setInterval> | null = null;
let zuletzt = 0;
let schreiben: Promise<void> = Promise.resolve();

// --- Gerätespeicher ---------------------------------------------------------------------------------------------

function oeffnen(): Promise<IDBDatabase> {
  return new Promise((fertig, fehler) => {
    const anfrage = indexedDB.open(speicherName(), 1);
    anfrage.onupgradeneeded = () => {
      const db = anfrage.result;
      db.createObjectStore("aufnahmen", { keyPath: "id" });
      db.createObjectStore("stuecke", { autoIncrement: true }).createIndex("aufnahme", "aufnahme");
    };
    anfrage.onsuccess = () => fertig(anfrage.result);
    anfrage.onerror = () => fehler(anfrage.error);
  });
}

async function vorgang<T>(speicher: string[], modus: IDBTransactionMode, arbeit: (t: IDBTransaction) => IDBRequest<T> | void): Promise<T | undefined> {
  const db = await oeffnen();
  return new Promise((fertig, fehler) => {
    const t = db.transaction(speicher, modus);
    const anfrage = arbeit(t);
    t.oncomplete = () => {
      db.close();
      fertig(anfrage ? anfrage.result : undefined);
    };
    t.onerror = () => {
      db.close();
      fehler(t.error);
    };
  });
}

function merken(a: Gespeichert): Promise<unknown> {
  return vorgang(["aufnahmen"], "readwrite", (t) => t.objectStore("aufnahmen").put($state.snapshot(a)));
}

function stueckAblegen(id: string, daten: Blob): Promise<unknown> {
  return vorgang(["stuecke"], "readwrite", (t) => t.objectStore("stuecke").add({ aufnahme: id, daten }));
}

export async function gespeicherte(): Promise<Gespeichert[]> {
  try {
    const liste = (await vorgang(["aufnahmen"], "readonly", (t) => t.objectStore("aufnahmen").getAll())) as Gespeichert[];
    return (liste ?? []).filter((a) => a.id !== aktuell?.id).sort((a, b) => b.beginn - a.beginn);
  } catch {
    return [];
  }
}

export async function alsDatei(id: string): Promise<{ daten: Blob; info: Gespeichert } | null> {
  const info = (await vorgang(["aufnahmen"], "readonly", (t) => t.objectStore("aufnahmen").get(id))) as Gespeichert | undefined;
  if (!info) return null;
  const stuecke = (await vorgang(["stuecke"], "readonly", (t) => t.objectStore("stuecke").index("aufnahme").getAll(id))) as
    { daten: Blob }[];
  return { daten: new Blob(stuecke.map((s) => s.daten), { type: info.typ }), info };
}

export async function verwerfen(id: string): Promise<void> {
  const schluessel = (await vorgang(["stuecke"], "readonly", (t) => t.objectStore("stuecke").index("aufnahme").getAllKeys(id))) as IDBValidKey[];
  await vorgang(["aufnahmen", "stuecke"], "readwrite", (t) => {
    t.objectStore("aufnahmen").delete(id);
    for (const k of schluessel ?? []) t.objectStore("stuecke").delete(k);
  });
}

// --- Mikrofone --------------------------------------------------------------------------------------------------

export async function geraeteLaden(): Promise<void> {
  try {
    aufnahme.geraet = localStorage.getItem(geraetMerker()) ?? "";
  } catch {
    // ohne Speicher das Standardgerät
  }
  if (!navigator.mediaDevices?.enumerateDevices) return;
  const liste = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "audioinput");
  aufnahme.geraete = liste.map((d, i) => ({ id: d.deviceId, name: d.label || (d.deviceId === "default" ? "Standard" : `Mikrofon ${i + 1}`) }));
}

async function mikrofon(geraet: string): Promise<MediaStream> {
  // automatische Lautstärke an: ohne sie kommt etwa am iPhone die Stimme um -30 dB an (Pegel und Erkennung leiden);
  // Echo- und Rauschunterdrückung aus, das Hörmodell bekommt den Ton möglichst unverfälscht
  const bedingung: MediaTrackConstraints = { echoCancellation: false, noiseSuppression: false, autoGainControl: true };
  if (geraet) bedingung.deviceId = { exact: geraet };
  return navigator.mediaDevices.getUserMedia({ audio: bedingung });
}

function anschliessen(s: MediaStream): void {
  if (!ton || !analyse || !ziel) return;
  quelle?.disconnect();
  quelle = ton.createMediaStreamSource(s);
  quelle.connect(analyse);
  quelle.connect(ziel);
  if (abgriff) quelle.connect(abgriff);
}

// Quelle wechseln, auch während der Aufnahme (die Weiche bleibt, nur der Eingang wird getauscht).
export async function quelleWechseln(geraet: string): Promise<void> {
  aufnahme.geraet = geraet;
  try {
    localStorage.setItem(geraetMerker(), geraet);
  } catch {
    // nur für diese Seite
  }
  if (!aufnahme.laeuft) return;
  try {
    const neu = await mikrofon(geraet);
    const alt = strom;
    anschliessen(neu);
    strom = neu;
    alt?.getTracks().forEach((t) => t.stop());
  } catch {
    aufnahme.fehler = "Dieses Mikrofon lässt sich nicht öffnen; die Aufnahme läuft mit dem bisherigen weiter.";
  }
}

// --- Aufnehmen --------------------------------------------------------------------------------------------------

function format(): { mime: string; endung: string } {
  for (const [mime, endung] of [["audio/webm;codecs=opus", ".webm"], ["audio/mp4", ".m4a"], ["audio/ogg;codecs=opus", ".ogg"]]) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(mime)) return { mime, endung };
  }
  return { mime: "", endung: ".webm" };
}

export function vorschlagName(): string {
  const d = new Date();
  const z = (n: number) => String(n).padStart(2, "0");
  return `${eingerichtet().name} ${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())} ${z(d.getHours())}-${z(d.getMinutes())}`;
}

export async function starten(): Promise<void> {
  aufnahme.fehler = "";
  if (!navigator.mediaDevices?.getUserMedia) {
    aufnahme.fehler = "Aufnehmen geht hier nicht (der Browser erlaubt das Mikrofon nur über HTTPS oder am Rechner selbst).";
    return;
  }
  // noch im Klick anlegen und fortsetzen: einen später angelegten Ton-Kontext hält Safari an (Pegel flach, Aufnahme stumm)
  ton = new AudioContext();
  void ton.resume().catch(() => undefined);
  try {
    strom = await mikrofon(aufnahme.geraet);
  } catch {
    try {
      strom = await mikrofon("");          // gemerktes Gerät nicht mehr da: das Standardgerät
      aufnahme.geraet = "";
    } catch {
      aufnahme.fehler = "Kein Zugriff aufs Mikrofon (im Browser erlauben).";
      void ton.close();
      ton = null;
      return;
    }
  }
  await geraeteLaden();                     // erst nach der Erlaubnis kennt der Browser die Namen
  if (ton.state !== "running") await ton.resume().catch(() => undefined);
  analyse = ton.createAnalyser();
  analyse.fftSize = 512;
  ziel = ton.createMediaStreamDestination();
  await liveVorbereiten(ton);              // immer bereit; der Schalter entscheidet, ob Text kommt
  anschliessen(strom);
  const { mime, endung } = format();
  rekorder = new MediaRecorder(ziel.stream, mime ? { mimeType: mime } : undefined);
  const name = vorschlagName();
  aktuell = { id: `${Date.now()}`, name: `${name}${endung}`, typ: rekorder.mimeType || mime || "audio/webm",
    beginn: Date.now(), dauer_ms: 0, marker: [], groesse: 0 };
  aufnahme.name = name;
  aufnahme.marker = [];
  lauf++;
  aufnahme.mitschrift = [];
  aufnahme.liveStand = "";
  await merken(aktuell);
  rekorder.ondataavailable = (e) => {
    if (!aktuell || !e.data.size) return;
    const a = aktuell;
    a.groesse += e.data.size;
    a.dauer_ms = aufnahme.dauer_ms;
    schreiben = schreiben.then(() => stueckAblegen(a.id, e.data)).then(() => merken(a)).then(() => undefined);
  };
  rekorder.start(STUECK_MS);
  aufnahme.laeuft = true;
  aufnahme.pausiert = false;
  aufnahme.dauer_ms = 0;
  arbeit.aufnahme = true;
  pegelMessen();
  zuletzt = performance.now();
  takt = setInterval(() => {
    const jetzt = performance.now();
    if (!aufnahme.pausiert) aufnahme.dauer_ms += jetzt - zuletzt;
    zuletzt = jetzt;
  }, 200);
  try {
    wachbleiben = await (navigator as unknown as { wakeLock?: { request(a: string): Promise<{ release(): Promise<void> }> } })
      .wakeLock?.request("screen") ?? null;
  } catch {
    wachbleiben = null;
  }
}

function pegelMessen(): void {
  if (!analyse) return;
  const a = analyse;
  const werte = new Float32Array(a.fftSize);
  let letzte = 0;
  let stillSeit = performance.now();
  aufnahme.signal = "ok";
  const schritt = (zeit: number) => {
    if (!aufnahme.laeuft) return;
    if (zeit - letzte > 100) {
      letzte = zeit;
      a.getFloatTimeDomainData(werte);
      let spitze = 0;
      for (const w of werte) spitze = Math.max(spitze, Math.abs(w));
      const db = spitze > 0 ? 20 * Math.log10(spitze) : -Infinity;
      const anteil = Math.max(0, Math.min(100, ((db - PEGEL_UNTEN_DB) / -PEGEL_UNTEN_DB) * 100));
      aufnahme.pegel = [...aufnahme.pegel.slice(1), aufnahme.pausiert ? 0 : anteil];
      if (aufnahme.pausiert || db >= STILL_DB) stillSeit = zeit;
      aufnahme.signal = ton && ton.state !== "running" ? "angehalten" : zeit - stillSeit > STILL_MELDEN_MS ? "still" : "ok";
    }
    requestAnimationFrame(schritt);
  };
  requestAnimationFrame(schritt);
}

/** Hält der Browser den Ton zurück (Signal "angehalten"), setzt ein Tippen ihn fort. */
export async function tonFortsetzen(): Promise<void> {
  await ton?.resume().catch(() => undefined);
}

export function pause(): void {
  if (!rekorder || !aufnahme.laeuft) return;
  if (aufnahme.pausiert) rekorder.resume();
  else {
    rekorder.pause();
    liveSchneiden(true);
  }
  aufnahme.pausiert = !aufnahme.pausiert;
}

export function markerSetzen(): void {
  if (!aktuell) return;
  const m = { zeit: Math.round(aufnahme.dauer_ms / 100) / 10, titel: `Marker ${aufnahme.marker.length + 1}` };
  aufnahme.marker = [...aufnahme.marker, m];
  aktuell.marker = $state.snapshot(aufnahme.marker);
  void merken(aktuell);
}

// Beenden: liefert die Aufnahme als Datei (sie bleibt im Gerät, bis `verwerfen` nach dem Hochladen sie entfernt).
export async function beenden(name: string): Promise<{ daten: Blob; info: Gespeichert } | null> {
  if (!rekorder || !aktuell) return null;
  const r = rekorder;
  const fertig = new Promise<void>((ok) => (r.onstop = () => ok()));
  r.stop();
  await fertig;
  await schreiben;
  liveSchneiden(true);
  const a = aktuell;
  a.dauer_ms = aufnahme.dauer_ms;
  const endung = a.name.slice(a.name.lastIndexOf("."));
  a.name = `${name.trim() || aufnahme.name}${endung}`;
  await merken(a);
  aufraeumen();
  return alsDatei(a.id);
}

/** Abbrechen während der Aufnahme: nichts wird gespeichert, auch die Stücke auf diesem Gerät gehen weg. */
export async function abbrechen(): Promise<void> {
  if (!rekorder || !aktuell) return;
  const r = rekorder;
  const a = aktuell;
  const fertig = new Promise<void>((ok) => (r.onstop = () => ok()));
  r.ondataavailable = null;
  r.stop();
  await fertig;
  await schreiben;
  lauf++;
  aufraeumen();
  aufnahme.mitschrift = [];
  aufnahme.marker = [];
  await verwerfen(a.id);
}

function aufraeumen(): void {
  strom?.getTracks().forEach((t) => t.stop());
  abgriff?.port.close();
  void ton?.close();
  void wachbleiben?.release().catch(() => {});
  if (takt) clearInterval(takt);
  rekorder = null;
  strom = null;
  ton = null;
  quelle = null;
  analyse = null;
  ziel = null;
  abgriff = null;
  wachbleiben = null;
  aktuell = null;
  takt = null;
  aufnahme.laeuft = false;
  aufnahme.pausiert = false;
  aufnahme.pegel = Array<number>(PEGEL).fill(0);
  arbeit.aufnahme = false;
}

// --- Live-Mitschrift --------------------------------------------------------------------------------------------

const ABGRIFF = `class Abgriff extends AudioWorkletProcessor {
  process(eingaenge) { const k = eingaenge[0] && eingaenge[0][0]; if (k) this.port.postMessage(k.slice(0)); return true; }
}
registerProcessor("abgriff", Abgriff);`;

let puffer: Float32Array[] = [];
let pufferLaenge = 0;
let stilleSeit = 0;
let stueckBeginn = 0;                   // Sekunden ab Beginn der Aufnahme
let rate = 48000;
let warteschlange: Promise<void> = Promise.resolve();

async function liveVorbereiten(t: AudioContext): Promise<void> {
  rate = t.sampleRate;
  puffer = [];
  pufferLaenge = 0;
  stilleSeit = 0;
  stueckBeginn = 0;
  try {
    const adresse = URL.createObjectURL(new Blob([ABGRIFF], { type: "text/javascript" }));
    await t.audioWorklet.addModule(adresse);
    URL.revokeObjectURL(adresse);
    abgriff = new AudioWorkletNode(t, "abgriff");
    abgriff.port.onmessage = (e: MessageEvent<Float32Array>) => aufnehmenLive(e.data);
    // stumm an den Ausgang: so verarbeitet der Browser den Abgriff sicher, zu hören ist nichts
    const stumm = t.createGain();
    stumm.gain.value = 0;
    abgriff.connect(stumm).connect(t.destination);
  } catch {
    abgriff = null;
    aufnahme.liveStand = "Live-Mitschrift geht in diesem Browser nicht; die Aufnahme läuft.";
  }
}

function aufnehmenLive(werte: Float32Array): void {
  if (!aufnahme.hoerbar || !aufnahme.live || aufnahme.pausiert || !aufnahme.laeuft) return;
  puffer.push(werte);
  pufferLaenge += werte.length;
  let summe = 0;
  for (const w of werte) summe += w * w;
  const leise = Math.sqrt(summe / werte.length) < STILLE_PEGEL;
  stilleSeit = leise ? stilleSeit + werte.length / rate : 0;
  const laenge = pufferLaenge / rate;
  if ((laenge >= LIVE_MIN_S && stilleSeit >= STILLE_S) || laenge >= LIVE_MAX_S) liveSchneiden(false);
}

function liveSchneiden(alles: boolean): void {
  if (!pufferLaenge || (!alles && pufferLaenge / rate < 1)) return;
  const roh = new Float32Array(pufferLaenge);
  let pos = 0;
  for (const p of puffer) {
    roh.set(p, pos);
    pos += p.length;
  }
  const beginn = stueckBeginn;
  const laenge = pufferLaenge / rate;
  stueckBeginn += laenge;
  puffer = [];
  pufferLaenge = 0;
  stilleSeit = 0;
  if (laenge < 0.8) return;
  const wav = alsWav(herunterrechnen(roh, rate));
  const meinLauf = lauf;
  warteschlange = warteschlange.then(() => hoeren(wav, beginn, laenge, meinLauf));
}

function herunterrechnen(roh: Float32Array, von: number): Float32Array {
  if (von === ZIEL_RATE) return roh;
  const faktor = von / ZIEL_RATE;
  const aus = new Float32Array(Math.floor(roh.length / faktor));
  for (let i = 0; i < aus.length; i++) {
    const a = Math.floor(i * faktor);
    const b = Math.min(roh.length, Math.floor((i + 1) * faktor));
    let summe = 0;
    for (let j = a; j < b; j++) summe += roh[j];
    aus[i] = summe / Math.max(1, b - a);
  }
  return aus;
}

function alsWav(werte: Float32Array): Blob {
  const puffer = new ArrayBuffer(44 + werte.length * 2);
  const v = new DataView(puffer);
  const text = (o: number, s: string) => [...s].forEach((z, i) => v.setUint8(o + i, z.charCodeAt(0)));
  text(0, "RIFF");
  v.setUint32(4, 36 + werte.length * 2, true);
  text(8, "WAVE");
  text(12, "fmt ");
  v.setUint32(16, 16, true);
  v.setUint16(20, 1, true);
  v.setUint16(22, 1, true);
  v.setUint32(24, ZIEL_RATE, true);
  v.setUint32(28, ZIEL_RATE * 2, true);
  v.setUint16(32, 2, true);
  v.setUint16(34, 16, true);
  text(36, "data");
  v.setUint32(40, werte.length * 2, true);
  for (let i = 0; i < werte.length; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, werte[i])) * 0x7fff, true);
  return new Blob([puffer], { type: "audio/wav" });
}

async function hoeren(wav: Blob, beginn: number, laenge: number, meinLauf: number): Promise<void> {
  const form = new FormData();
  form.append("datei", wav, "live.wav");
  aufnahme.liveStand = "hört ...";
  try {
    const antwort = await fetch(`/api/v1${eingerichtet().hoeren}`, { method: "POST", body: form, headers: { "X-Kellerwolke-Sitzung": token() } });
    if (!antwort.ok) {
      let meldung = `Fehler ${antwort.status}`;
      try {
        meldung = (await antwort.json()).detail ?? meldung;
      } catch {
        // Text bleibt
      }
      aufnahme.liveStand = antwort.status === 503 ? `wartet auf den Hördienst (${meldung})` : meldung;
      return;
    }
    const daten = (await antwort.json()) as { text: string };
    if (meinLauf !== lauf) return;
    if (daten.text.trim()) aufnahme.mitschrift = [...aufnahme.mitschrift, { start: beginn, ende: beginn + laenge, text: daten.text.trim() }];
    aufnahme.liveStand = "";
  } catch {
    aufnahme.liveStand = "keine Verbindung zur App";
  }
}
