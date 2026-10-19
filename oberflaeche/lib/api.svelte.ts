// Anfragen an das Backend der eigenen App. Der Token der Kellerwolke liegt im Gerät (localStorage) und geht im Kopf
// X-Kellerwolke-Sitzung mit; endet die Sitzung (401), meldet sich die Anmeldung. Ereignisströme laufen über fetch,
// damit auch dort der Kopf mitgeht.
//
// Jede Anfrage hat eine Zeitgrenze (Vorgabe 20 s, `anfragenEinstellen`, je Anfrage `zeitgrenzeMs`, 0 heißt ohne).
// Gleiche GET-Anfragen, die schon unterwegs sind, gehen nur einmal hinaus; jeder Aufrufer bekommt sein eigenes
// Ergebnis. Ein Abbruchsignal (`signal`, etwa `seitenSignal()` einer Seite) beendet nur das Warten dieses Aufrufers;
// die Anfrage selbst endet, wenn niemand mehr auf sie wartet. Ob die App überhaupt antwortet, führt
// `erreichbar.svelte.ts` an einer Stelle; Seiten zeigen das nicht noch einmal (`seitenFehler`).
import { onDestroy } from "svelte";
import {
  ANTWORTET_NICHT, geantwortet, KEINE_VERBINDUNG, nichtErreicht, vomVorschaltdienst, zeitgrenze, zeitgrenzeSetzen,
  zuLangsam,
} from "./erreichbar.svelte";

export { verbindung } from "./erreichbar.svelte";

// Wie eine Anfrage endete, wenn nicht mit einer Antwort der App: `weg` (keine Verbindung), `zeit` (Zeitgrenze),
// `abgebrochen` (der Aufrufer wartet nicht mehr, etwa weil die Seite verlassen wurde).
export type FehlerArt = "antwort" | "weg" | "zeit" | "abgebrochen";

export class ApiFehler extends Error {
  status: number;
  art: FehlerArt;
  constructor(status: number, nachricht: string, art: FehlerArt = "antwort") {
    super(nachricht);
    this.status = status;
    this.art = art;
  }

  // Die App hat nicht geantwortet (weg oder zu langsam); das zeigt die Schale an einer Stelle.
  get ohneAntwort(): boolean {
    return this.art === "weg" || this.art === "zeit";
  }
}

// `zeitgrenzeMs`: Zeitgrenze dieser Anfrage (statt der Vorgabe), 0 heißt ohne.
export type AnfrageOptionen = RequestInit & { zeitgrenzeMs?: number };

let schluessel = "app_sitzung";
let beiSitzungsende: (() => void) | null = null;

export function einrichten(kennung: string, sitzungsende: () => void): void {
  schluessel = `${kennung}_sitzung`;
  beiSitzungsende = sitzungsende;
}

// Für die ganze Oberfläche einer App, etwa im Einstieg: `anfragenEinstellen({ zeitgrenzeMs: 30000 })`.
export function anfragenEinstellen(werte: { zeitgrenzeMs?: number }): void {
  if (werte.zeitgrenzeMs !== undefined) zeitgrenzeSetzen(werte.zeitgrenzeMs);
}

// Abfrageteil einer Adresse aus Werten; leere fallen weg, Listen werden wiederholt (?zustand=a&zustand=b).
export function abfrage(werte: Record<string, string | number | boolean | null | undefined | string[]>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(werte)) {
    if (Array.isArray(v)) v.forEach((x) => p.append(k, x));
    else if (v !== null && v !== undefined && v !== "") p.set(k, String(v));
  }
  const text = p.toString();
  return text ? `?${text}` : "";
}

export function token(): string {
  try {
    return localStorage.getItem(schluessel) ?? "";
  } catch {
    return "";
  }
}

export function setzeToken(wert: string): void {
  try {
    if (wert) localStorage.setItem(schluessel, wert);
    else localStorage.removeItem(schluessel);
  } catch {
    // ohne Speicher gilt die Anmeldung nur für diese Seite
  }
}

// Im Skript einer Seite (oder eines ihrer Teile) aufrufen: das Signal bricht ab, sobald sie ausgebaut wird, also beim
// Verlassen. An `hole(pfad, { signal })` geben; so wartet keine verlassene Seite mehr auf ihre Antworten.
export function seitenSignal(): AbortSignal {
  const steuerung = new AbortController();
  onDestroy(() => steuerung.abort());
  return steuerung.signal;
}

// Text eines Fehlers für die Seite; leer, wenn die App nicht antwortet (das zeigt die Schale) oder die Seite den
// Aufruf selbst abgebrochen hat.
export function seitenFehler(f: unknown): string {
  if (f instanceof ApiFehler && (f.ohneAntwort || f.art === "abgebrochen")) return "";
  return f instanceof Error ? f.message : String(f);
}

interface Antwort {
  status: number;
  ok: boolean;
  statusText: string;
  text: string;
}

function fehlerAus(antwort: Antwort): ApiFehler {
  let text = antwort.statusText;
  try {
    const daten = JSON.parse(antwort.text);
    if (typeof daten.detail === "string") text = daten.detail;
  } catch {
    // Text bleibt
  }
  return new ApiFehler(antwort.status, text);
}

// Eine Anfrage bis zur ganz gelesenen Antwort, mit Zeitgrenze; meldet, ob die App geantwortet hat.
async function senden(pfad: string, init: AnfrageOptionen, signal: AbortSignal): Promise<Antwort> {
  const { zeitgrenzeMs = zeitgrenze(), ...rest } = init;
  const steuerung = new AbortController();
  let abgelaufen = false;
  const uhr = zeitgrenzeMs > 0 ? setTimeout(() => ((abgelaufen = true), steuerung.abort()), zeitgrenzeMs) : null;
  const weiter = () => steuerung.abort();
  if (signal.aborted) steuerung.abort();
  signal.addEventListener("abort", weiter, { once: true });
  try {
    const antwort = await fetch(`/api/v1${pfad}`, {
      ...rest,
      signal: steuerung.signal,
      headers: { "Content-Type": "application/json", "X-Kellerwolke-Sitzung": token(), ...(rest.headers ?? {}) },
    });
    const text = await antwort.text();
    if (vomVorschaltdienst(antwort)) {
      nichtErreicht(ANTWORTET_NICHT);
      throw new ApiFehler(antwort.status, ANTWORTET_NICHT, "weg");
    }
    geantwortet();
    return { status: antwort.status, ok: antwort.ok, statusText: antwort.statusText, text };
  } catch (f) {
    if (f instanceof ApiFehler) throw f;
    if (abgelaufen) {
      zuLangsam();
      throw new ApiFehler(0, `${ANTWORTET_NICHT} (keine Antwort nach ${Math.round(zeitgrenzeMs / 1000)} s)`, "zeit");
    }
    if (steuerung.signal.aborted) throw new ApiFehler(0, "Abgebrochen", "abgebrochen");
    nichtErreicht(KEINE_VERBINDUNG);
    throw new ApiFehler(0, KEINE_VERBINDUNG, "weg");
  } finally {
    if (uhr) clearTimeout(uhr);
    signal.removeEventListener("abort", weiter);
  }
}

// Gleiche GET-Anfragen, die gerade unterwegs sind: eine gemeinsame Antwort, beendet, wenn niemand mehr wartet.
interface Unterwegs {
  kennung: string;
  antwort: Promise<Antwort>;
  steuerung: AbortController;
  wartende: number;
}
const unterwegs = new Map<string, Unterwegs>();

function gemeinsam(pfad: string, init: AnfrageOptionen): Promise<Antwort> {
  const kennung = `${pfad}\n${token()}\n${init.zeitgrenzeMs ?? ""}\n${JSON.stringify(init.headers ?? {})}`;
  let u = unterwegs.get(kennung);
  if (!u) {
    const steuerung = new AbortController();
    const neu: Unterwegs = { kennung, antwort: senden(pfad, { ...init, signal: undefined }, steuerung.signal), steuerung, wartende: 0 };
    neu.antwort.catch(() => {}).finally(() => vergessen(neu));
    unterwegs.set(kennung, neu);
    u = neu;
  }
  return warten(u, init.signal ?? undefined);
}

function vergessen(u: Unterwegs): void {
  if (unterwegs.get(u.kennung) === u) unterwegs.delete(u.kennung);
}

function warten(u: Unterwegs, signal: AbortSignal | undefined): Promise<Antwort> {
  u.wartende += 1;
  if (!signal) return u.antwort;                       // wartet bis zum Ende: die Anfrage endet nie vorher
  return new Promise<Antwort>((fertig, fehler) => {
    const aufgeben = () => {
      u.wartende -= 1;
      if (u.wartende === 0) {
        vergessen(u);                                  // wer jetzt kommt, fragt neu statt eine abgebrochene zu teilen
        u.steuerung.abort();
      }
      fehler(new ApiFehler(0, "Abgebrochen", "abgebrochen"));
    };
    if (signal.aborted) return aufgeben();
    signal.addEventListener("abort", aufgeben, { once: true });
    u.antwort.then(fertig, fehler).finally(() => signal.removeEventListener("abort", aufgeben));
  });
}

export async function hole<T>(pfad: string, init: AnfrageOptionen = {}): Promise<T> {
  const lesend = (init.method ?? "GET").toUpperCase() === "GET" && !init.body;
  const antwort = lesend ? await gemeinsam(pfad, init) : await senden(pfad, init, init.signal ?? new AbortController().signal);
  if (antwort.status === 401 && token()) {
    setzeToken("");
    beiSitzungsende?.();
  }
  if (!antwort.ok) throw fehlerAus(antwort);
  if (antwort.status === 204 || !antwort.text) return undefined as T;
  return JSON.parse(antwort.text) as T;               // je Aufrufer ein eigenes Ergebnis
}

export const json = (daten: unknown): RequestInit => ({ body: JSON.stringify(daten) });

// Server-Sent Events über fetch: liefert je Ereignis (Art, Daten); endet mit der Verbindung oder dem Abbruchsignal.
export async function* ereignisse(pfad: string, signal: AbortSignal): AsyncGenerator<{ art: string; daten: string }> {
  let antwort: Response;
  try {
    antwort = await fetch(`/api/v1${pfad}`, { headers: { "X-Kellerwolke-Sitzung": token() }, signal });
  } catch (f) {
    if (!signal.aborted) nichtErreicht(KEINE_VERBINDUNG);
    throw f;
  }
  if (vomVorschaltdienst(antwort)) {
    nichtErreicht(ANTWORTET_NICHT);
    throw new ApiFehler(antwort.status, ANTWORTET_NICHT, "weg");
  }
  geantwortet();
  if (!antwort.ok || !antwort.body) {
    throw fehlerAus({ status: antwort.status, ok: antwort.ok, statusText: antwort.statusText, text: await antwort.text() });
  }
  const leser = antwort.body.pipeThrough(new TextDecoderStream()).getReader();
  let puffer = "";
  while (true) {
    const { value, done } = await leser.read();
    if (done) return;
    puffer += value;
    let ende: number;
    while ((ende = puffer.indexOf("\n\n")) >= 0) {
      const block = puffer.slice(0, ende);
      puffer = puffer.slice(ende + 2);
      let art = "message";
      const daten: string[] = [];
      for (const zeile of block.split("\n")) {
        if (zeile.startsWith("event: ")) art = zeile.slice(7);
        else if (zeile.startsWith("data: ")) daten.push(zeile.slice(6));
      }
      if (daten.length) yield { art, daten: daten.join("\n") };
    }
  }
}
