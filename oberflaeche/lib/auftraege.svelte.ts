// Aufträge der App: Liste nach Filter, Zähler für Kopf und Navigation, laufend nachgeführt über den Ereignisstrom.
// Gezählt wird in einer Anfrage (`/auftraege/zahlen`), nur wenn ein Auftrag seinen Zustand wechselt, und höchstens
// einmal je Sekunde (Ereignisse dazwischen werden gesammelt).
import { ereignisse, hole, json } from "./api.svelte";
import { rueckkehr, verbindung } from "./erreichbar.svelte";
import type { Auftrag, Seite, Zahlen, Zustand } from "./typen";

export type Filter = "alle" | "offen" | "fertig" | "fehler";
const ZUSTAENDE: Record<Filter, Zustand[]> = {
  alle: [],
  offen: ["wartet", "laeuft"],
  fertig: ["fertig"],
  fehler: ["fehler", "abgebrochen", "unterbrochen"],
};
const SEITE = 50;
const ZAEHLEN_MS = 1000;
const ERSTE_PAUSE_MS = 2000;
const LAENGSTE_PAUSE_MS = 60000;

export const auftraege = $state<{
  liste: Auftrag[];
  gesamt: number;
  filter: Filter;
  suche: string;
  gewaehlt: string | null;
  laufen: number;
  warten: number;
  fehler: number;
}>({ liste: [], gesamt: 0, filter: "offen", suche: "", gewaehlt: null, laufen: 0, warten: 0, fehler: 0 });

function abfrage(filter: Filter, grenze: number, versatz = 0): string {
  const p = new URLSearchParams({ grenze: String(grenze), versatz: String(versatz) });
  for (const z of ZUSTAENDE[filter]) p.append("zustand", z);
  if (auftraege.suche.trim()) p.set("suche", auftraege.suche.trim());
  return `/auftraege?${p}`;
}

// `signal`: etwa `seitenSignal()` der Seite, die lädt.
export async function laden(signal?: AbortSignal): Promise<void> {
  const seite = await hole<Seite<Auftrag>>(abfrage(auftraege.filter, SEITE), { signal });
  auftraege.liste = seite.eintraege;
  auftraege.gesamt = seite.gesamt;
  if (!seite.eintraege.some((a) => a.id === auftraege.gewaehlt)) auftraege.gewaehlt = seite.eintraege[0]?.id ?? null;
}

export async function mehrLaden(signal?: AbortSignal): Promise<void> {
  const seite = await hole<Seite<Auftrag>>(abfrage(auftraege.filter, SEITE, auftraege.liste.length), { signal });
  auftraege.liste = [...auftraege.liste, ...seite.eintraege.filter((a) => !auftraege.liste.some((b) => b.id === a.id))];
  auftraege.gesamt = seite.gesamt;
}

async function zaehlen(): Promise<void> {
  const z = await hole<Zahlen>("/auftraege/zahlen");
  [auftraege.laufen, auftraege.warten, auftraege.fehler] = [z.laeuft, z.wartet, z.fehler];
}

// Höchstens eine Zählung je Sekunde und nie zwei gleichzeitig; was dazwischen kommt, zählt die nächste mit.
let zuletzt = 0;
let geplant: ReturnType<typeof setTimeout> | null = null;
let zaehlung: Promise<void> | null = null;
let nochmal = false;

function zaehlenBald(): void {
  if (zaehlung) {
    nochmal = true;
    return;
  }
  if (geplant) return;
  geplant = setTimeout(() => {
    geplant = null;
    void zaehlenJetzt();
  }, Math.max(0, zuletzt + ZAEHLEN_MS - Date.now()));
}

async function zaehlenJetzt(): Promise<void> {
  if (zaehlung) {
    nochmal = true;
    return zaehlung;
  }
  if (geplant) clearTimeout(geplant);
  geplant = null;
  zuletzt = Date.now();
  zaehlung = zaehlen().catch(() => {});
  await zaehlung;
  zaehlung = null;
  if (nochmal) {
    nochmal = false;
    zaehlenBald();
  }
}

// Zuletzt gesehener Zustand je Auftrag: Fortschritt allein ändert keine Zahl.
const gesehen = new Map<string, Zustand>();
function zustandGesehen(a: Auftrag): boolean {
  if (gesehen.get(a.id) === a.zustand) return false;
  if (gesehen.size > 2000) gesehen.clear();
  gesehen.set(a.id, a.zustand);
  return true;
}

// Seiten der App hören mit, um ihren eigenen Stand nachzuführen (etwa eine Aufnahme als "transkribiert").
const hoerer = new Set<(a: Auftrag) => void>();

export function beiAuftrag(fn: (a: Auftrag) => void): () => void {
  hoerer.add(fn);
  return () => hoerer.delete(fn);
}

function einpflegen(a: Auftrag): void {
  for (const fn of hoerer) {
    try {
      fn(a);
    } catch {
      // ein Hörer darf den Strom nie anhalten
    }
  }
  const passt = ZUSTAENDE[auftraege.filter].length === 0 || ZUSTAENDE[auftraege.filter].includes(a.zustand);
  const i = auftraege.liste.findIndex((b) => b.id === a.id);
  if (i >= 0) auftraege.liste[i] = a;
  else if (passt && !auftraege.suche.trim()) {
    auftraege.liste = [a, ...auftraege.liste];
    auftraege.gesamt += 1;
    if (!auftraege.liste.some((b) => b.id === auftraege.gewaehlt)) auftraege.gewaehlt = a.id;
  }
}

// Folgt dem Ereignisstrom, bis die zurückgegebene Funktion ihn beendet; nach einem Abriss mit wachsender Pause neu
// (2 s, doppelt so lange, höchstens 60 s), und solange die App nicht antwortet, erst nach ihrer Rückkehr.
// Verlässt man die Seite, schließt der Strom: eine Seite im Zwischenspeicher für Zurück hielte ihn sonst offen und
// belegte eine der wenigen Verbindungen je Server (gemessen: neue Seiten warteten dann bis zu 30 s). Kommt sie aus dem
// Zwischenspeicher zurück, folgt sie wieder und zählt neu.
export function verfolgen(): () => void {
  let beendet = false;
  let strom: AbortController | null = null;
  let laeuft = false;

  async function folgen() {
    if (laeuft) return;
    laeuft = true;
    let pause = ERSTE_PAUSE_MS;
    while (!beendet) {
      const diese = (strom = new AbortController());
      try {
        gesehen.clear();
        await zaehlenJetzt();
        for await (const e of ereignisse("/auftraege/ereignisse", diese.signal)) {
          pause = ERSTE_PAUSE_MS;
          if (e.art === "auftrag") {
            const a = JSON.parse(e.daten) as Auftrag;
            einpflegen(a);
            if (zustandGesehen(a)) zaehlenBald();
          }
        }
      } catch {
        // Verbindung weg oder abgebrochen
      }
      if (beendet || diese.signal.aborted) break;      // beendet oder Seite verlassen
      if (!verbindung.ok) await rueckkehr(diese.signal);
      else await new Promise((r) => setTimeout(r, pause));
      pause = Math.min(pause * 2, LAENGSTE_PAUSE_MS);
    }
    laeuft = false;
  }

  const verlassen = () => strom?.abort();
  const wieder = (e: PageTransitionEvent) => {
    if (e.persisted) void folgen();
  };
  addEventListener("pagehide", verlassen);
  addEventListener("pageshow", wieder);
  void folgen();
  return () => {
    beendet = true;
    strom?.abort();
    removeEventListener("pagehide", verlassen);
    removeEventListener("pageshow", wieder);
  };
}

export async function abbrechen(id: string): Promise<void> {
  einpflegen(await hole<Auftrag>(`/auftraege/${id}/abbrechen`, { method: "POST" }));
}

export async function wiederholen(id: string): Promise<void> {
  const neu = await hole<Auftrag>(`/auftraege/${id}/wiederholen`, { method: "POST", ...json({}) });
  einpflegen(neu);
  auftraege.gewaehlt = neu.id;
}

export async function entfernen(id: string): Promise<void> {
  await hole(`/auftraege/${id}`, { method: "DELETE" });
  auftraege.liste = auftraege.liste.filter((a) => a.id !== id);
  auftraege.gesamt = Math.max(0, auftraege.gesamt - 1);
  if (auftraege.gewaehlt === id) auftraege.gewaehlt = auftraege.liste[0]?.id ?? null;
}

// Stand je Phase für die Schrittanzeige.
export type PhasenStand = "fertig" | "jetzt" | "fehler" | "offen";
export function phasenStand(a: Auftrag): PhasenStand[] {
  if (a.zustand === "fertig") return a.phasen.map(() => "fertig");
  const jetzt = a.phase ? a.phasen.findIndex((p) => p.schluessel === a.phase) : a.zustand === "laeuft" ? 0 : -1;
  return a.phasen.map((_, i) => {
    if (jetzt < 0 || i > jetzt) return "offen";
    if (i < jetzt) return "fertig";
    return a.zustand === "laeuft" ? "jetzt" : a.zustand === "wartet" ? "offen" : "fehler";
  });
}
