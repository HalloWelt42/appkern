// Vorlesen in der Oberfläche jeder App. Die App reicht den Strom der Vertonung durch (Baustein `appkern.vorlesen`, der
// eine Weg zur Sprachausgabe): ein POST an einen Weg der App, je Zeile ein JSON (`satz` mit dem Ton als
// Base64-WAV und dem Text, `ende`, `fehler`). Hier wird Satz für Satz lückenlos gespielt (ein AudioContext, die Sätze
// vorausgeplant, nie ein Tonelement je Satz) und der laufende Satz gemeldet. Gespielt wird mit Vorlauf (vorlauf.ts):
// erst, wenn genug Ton bereitliegt; ist der Sprechdienst ausgelastet, mehr, und reißt der Ton ab, wartet der Vorleser,
// bis wieder genug da ist. Gestartet wird im Tippen (`umschalten`), sonst bleibt der Ton am iPhone stumm; ein zweites
// Tippen auf dieselbe Kennung hält an. Immer nur eines spielt: beginnt das Vorlesen, hält der Einzelton an, und beginnt
// ein Ton- oder Videoelement der Seite, endet das Vorlesen. Ob die App eine Vertonung eingetragen hat, sagt
// `vorlesbar.da` (einmal geholt mit `vorlesbarPruefen`).
import { hole, token } from "./api.svelte";
import { Vorlauf } from "./vorlauf";
import { einzelton } from "./wiedergabe.svelte";

export interface VorleseSatz {
  nr: number;
  text: string;
}

/** Pause zwischen zwei Sätzen (wie beim Sprechen am Stück) */
const PAUSE_S = 0.3;

function tonAus(basis64: string): ArrayBuffer {
  const roh = atob(basis64);
  const bytes = new Uint8Array(roh.length);
  for (let i = 0; i < roh.length; i++) bytes[i] = roh.charCodeAt(i);
  return bytes.buffer;
}

async function grundAus(antwort: Response): Promise<string> {
  try {
    const daten = (await antwort.json()) as { detail?: unknown };
    if (typeof daten.detail === "string") return daten.detail;
  } catch {
    // kein JSON
  }
  return `Vorlesen ging nicht (${antwort.status})`;
}

class Vorleser {
  /** Was gerade vorgelesen wird (Kennung, die die App vergibt), sonst null */
  kennung = $state<string | null>(null);
  /** Der erste Satz ist noch nicht da (er wird gerade gesprochen) */
  wartet = $state(false);
  /** Der Satz, der gerade klingt */
  satz = $state<VorleseSatz | null>(null);
  /** Warum das letzte Vorlesen nicht ging oder abbrach; leer, wenn alles gut ging */
  fehler = $state("");
  #ctx: AudioContext | null = null;
  #steuerung: AbortController | null = null;
  #quellen: AudioBufferSourceNode[] = [];
  #lauf = 0;
  #wacht = false;
  /** Vorlauf über die Läufe gemerkt: nach einem Abriss mehr, nach Läufen ohne langsam wieder weniger */
  #vorlauf = new Vorlauf();

  /** Liest den Strom von `pfad` (unter /api/v1, POST mit `daten`) unter `kennung` vor; liest dieselbe Kennung schon,
   *  hält es an. Im Klick aufrufen. */
  umschalten(kennung: string, pfad: string, daten: unknown): void {
    if (this.kennung === kennung) this.anhalten();
    else void this.starten(kennung, pfad, daten);
  }

  /** Schaltet den Ton im Tippen frei, wenn der Text erst danach geladen wird (am iPhone bleibt Ton sonst stumm, der
   *  nicht im Tippen beginnt); dann `starten`. */
  entsperren(): AudioContext {
    const ctx = (this.#ctx ??= new AudioContext());
    void ctx.resume().catch(() => undefined);
    return ctx;
  }

  async starten(kennung: string, pfad: string, daten: unknown): Promise<void> {
    this.anhalten();
    einzelton.anhalten();
    this.#wachen();
    const ctx = this.entsperren();                          // noch im Tippen, sonst bleibt es am iPhone stumm
    const lauf = ++this.#lauf;
    const steuerung = new AbortController();
    this.#steuerung = steuerung;
    Object.assign(this, { kennung, wartet: true, satz: null, fehler: "" });
    let zeitpunkt = 0;
    let offen = 0;
    let fertig = false;
    /** angekommene Sätze, die noch auf den Vorlauf warten */
    let bereit: { puffer: AudioBuffer; satz: VorleseSatz }[] = [];
    let spielt = false;
    const jetzt = (): number => performance.now() / 1000;
    const vorlauf = this.#vorlauf;
    vorlauf.beginnen(jetzt());
    const einplanen = (puffer: AudioBuffer, satz: VorleseSatz): void => {
      const quelle = ctx.createBufferSource();
      quelle.buffer = puffer;
      quelle.connect(ctx.destination);
      zeitpunkt = Math.max(zeitpunkt, ctx.currentTime + 0.05);
      const beginn = zeitpunkt;
      quelle.start(beginn);
      zeitpunkt += puffer.duration + PAUSE_S;
      offen++;
      this.#quellen.push(quelle);
      setTimeout(() => {
        if (lauf !== this.#lauf) return;
        this.satz = satz;
        this.wartet = false;
      }, Math.max(0, (beginn - ctx.currentTime) * 1000));
      quelle.onended = () => {
        offen--;
        vorbei();
      };
    };
    /** Spielt, was bereitliegt, sobald der Vorlauf es erlaubt (oder der Text zu Ende ist) */
    const weiter = (): void => {
      if (!spielt) {
        const bereitS = bereit.reduce((s, b) => s + b.puffer.duration, 0);
        if (!bereit.length || !vorlauf.genug(bereitS, jetzt(), fertig)) return;
        spielt = true;
      }
      for (const b of bereit) einplanen(b.puffer, b.satz);
      bereit = [];
    };
    const vorbei = (): void => {
      if (lauf !== this.#lauf || !fertig || offen > 0 || bereit.length) return;
      vorlauf.beenden();
      this.#beenden(lauf);
    };
    try {
      const antwort = await fetch(`/api/v1${pfad}`, {
        method: "POST", body: JSON.stringify(daten), signal: steuerung.signal,
        headers: { "Content-Type": "application/json", "X-Kellerwolke-Sitzung": token() },
      });
      if (!antwort.ok || !antwort.body) {
        if (lauf === this.#lauf) this.fehler = await grundAus(antwort);
        this.#beenden(lauf);
        return;
      }
      const leser = antwort.body.pipeThrough(new TextDecoderStream()).getReader();
      let rest = "";
      for (;;) {
        const { value, done } = await leser.read();
        if (done || lauf !== this.#lauf) break;
        rest += value;
        for (let i = rest.indexOf("\n"); i >= 0; i = rest.indexOf("\n")) {
          const zeile = rest.slice(0, i).trim();
          rest = rest.slice(i + 1);
          if (!zeile) continue;
          const z = JSON.parse(zeile) as { art: string; nr?: number; text?: string; ton?: string; meldung?: string };
          if (z.art === "satz" && z.ton) {
            const puffer = await ctx.decodeAudioData(tonAus(z.ton));
            if (lauf !== this.#lauf) return;
            vorlauf.angekommen(puffer.duration);
            // abgerissen: alles Eingeplante ist verklungen, bevor dieser Satz kam; dann erst wieder mit Vorlauf
            if (spielt && offen === 0 && ctx.currentTime > zeitpunkt) {
              vorlauf.abgerissen();
              spielt = false;
              this.wartet = true;
            }
            bereit.push({ puffer, satz: { nr: z.nr ?? 0, text: z.text ?? "" } });
            weiter();
          } else if (z.art === "fehler") {
            this.fehler = z.meldung || "Vorlesen brach ab";
            fertig = true;
          } else if (z.art === "ende") {
            fertig = true;
          }
        }
      }
      fertig = true;
      weiter();
      vorbei();
    } catch {
      if (lauf === this.#lauf && !steuerung.signal.aborted) {
        this.fehler = "Vorlesen brach ab: keine Verbindung zur App";
        this.#beenden(lauf);
      }
    }
  }

  /** Hält an: was noch klingt, verstummt; was noch kommt, wird nicht mehr gelesen. */
  anhalten(): void {
    this.#lauf++;
    this.#steuerung?.abort();
    this.#steuerung = null;
    for (const q of this.#quellen) {
      try {
        q.stop();
      } catch {
        // schon zu Ende
      }
    }
    this.#quellen = [];
    Object.assign(this, { kennung: null, wartet: false, satz: null });
  }

  #beenden(lauf: number): void {
    if (lauf !== this.#lauf) return;
    this.#steuerung = null;
    this.#quellen = [];
    Object.assign(this, { kennung: null, wartet: false, satz: null });
  }

  /** Beginnt ein Ton- oder Videoelement der Seite (auch der Einzelton), endet das Vorlesen. */
  #wachen(): void {
    if (this.#wacht) return;
    this.#wacht = true;
    document.addEventListener("play", (e) => {
      if (e.target instanceof HTMLMediaElement && this.kennung) this.anhalten();
    }, true);
  }
}

export const vorleser = new Vorleser();

/** Ist in dieser App eine Vertonung zum Vorlesen eingetragen? `null`: noch nicht gefragt */
export const vorlesbar = $state<{ da: boolean | null }>({ da: null });
let gefragt: Promise<void> | null = null;

/** Fragt einmal je Seite den Weg `GET /vorlesen` der App (aus `appkern.vorlesen`); ohne Weg gilt: nicht da. */
export function vorlesbarPruefen(neu = false): Promise<void> {
  if (!gefragt || neu) {
    gefragt = hole<{ da: boolean }>("/vorlesen")
      .then((a) => { vorlesbar.da = a.da; })
      .catch(() => { vorlesbar.da = false; });
  }
  return gefragt;
}
