// Aufträge der App: Liste nach Filter, Zähler für Kopf und Navigation, laufend nachgeführt über den Ereignisstrom.
import { ereignisse, hole, json } from "./api.svelte";
import type { Auftrag, Seite, Zustand } from "./typen";

export type Filter = "alle" | "offen" | "fertig" | "fehler";
const ZUSTAENDE: Record<Filter, Zustand[]> = {
  alle: [],
  offen: ["wartet", "laeuft"],
  fertig: ["fertig"],
  fehler: ["fehler", "abgebrochen", "unterbrochen"],
};
const SEITE = 50;

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

export async function laden(): Promise<void> {
  const seite = await hole<Seite<Auftrag>>(abfrage(auftraege.filter, SEITE));
  auftraege.liste = seite.eintraege;
  auftraege.gesamt = seite.gesamt;
  if (!seite.eintraege.some((a) => a.id === auftraege.gewaehlt)) auftraege.gewaehlt = seite.eintraege[0]?.id ?? null;
}

export async function mehrLaden(): Promise<void> {
  const seite = await hole<Seite<Auftrag>>(abfrage(auftraege.filter, SEITE, auftraege.liste.length));
  auftraege.liste = [...auftraege.liste, ...seite.eintraege.filter((a) => !auftraege.liste.some((b) => b.id === a.id))];
  auftraege.gesamt = seite.gesamt;
}

async function zaehlen(): Promise<void> {
  const anzahl = async (z: Zustand[]) => {
    const p = new URLSearchParams({ grenze: "1" });
    z.forEach((x) => p.append("zustand", x));
    return (await hole<Seite<Auftrag>>(`/auftraege?${p}`)).gesamt;
  };
  [auftraege.laufen, auftraege.warten, auftraege.fehler] = await Promise.all([
    anzahl(["laeuft"]),
    anzahl(["wartet"]),
    anzahl(["fehler"]),
  ]);
}

let zaehlTakt: ReturnType<typeof setTimeout> | null = null;
function spaeterZaehlen(): void {
  if (zaehlTakt) clearTimeout(zaehlTakt);
  zaehlTakt = setTimeout(() => zaehlen().catch(() => {}), 400);
}

function einpflegen(a: Auftrag): void {
  const passt = ZUSTAENDE[auftraege.filter].length === 0 || ZUSTAENDE[auftraege.filter].includes(a.zustand);
  const i = auftraege.liste.findIndex((b) => b.id === a.id);
  if (i >= 0) auftraege.liste[i] = a;
  else if (passt && !auftraege.suche.trim()) {
    auftraege.liste = [a, ...auftraege.liste];
    auftraege.gesamt += 1;
    if (!auftraege.liste.some((b) => b.id === auftraege.gewaehlt)) auftraege.gewaehlt = a.id;
  }
}

// Folgt dem Ereignisstrom, bis `stoppen()` gerufen wird; nach einem Abriss mit wachsender Pause neu.
export function verfolgen(): () => void {
  const abbruch = new AbortController();
  (async () => {
    let pause = 1000;
    while (!abbruch.signal.aborted) {
      try {
        await zaehlen();
        for await (const e of ereignisse("/auftraege/ereignisse", abbruch.signal)) {
          pause = 1000;
          if (e.art === "auftrag") {
            einpflegen(JSON.parse(e.daten) as Auftrag);
            spaeterZaehlen();
          }
        }
      } catch {
        // Verbindung weg oder abgebrochen
      }
      if (abbruch.signal.aborted) return;
      await new Promise((r) => setTimeout(r, pause));
      pause = Math.min(pause * 2, 30000);
    }
  })();
  return () => abbruch.abort();
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
