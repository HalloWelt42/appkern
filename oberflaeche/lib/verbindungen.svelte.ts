// Verbindungen der App (Kellerwolke, Leitstelle), alle 30 s geprüft; nie zwei Prüfungen gleichzeitig, und solange
// die App selbst nicht antwortet, ruht die Prüfung (das zeigt die Schale an einer Stelle).
import { hole } from "./api.svelte";
import { takt, type Takt } from "./takt";
import type { Verbindung } from "./typen";

const TAKT_MS = 30000;
export const verbindungen = $state<{ liste: Verbindung[]; geprueft: boolean; prueft: boolean }>(
  { liste: [], geprueft: false, prueft: false });

let laufend: Takt | null = null;
let einzeln: Promise<void> | null = null;

async function abfragen(): Promise<void> {
  verbindungen.prueft = true;
  try {
    verbindungen.liste = await hole<Verbindung[]>("/verbindungen");
  } finally {
    verbindungen.prueft = false;
    verbindungen.geprueft = true;
  }
}

// Sofort prüfen (etwa "Erneut prüfen"); läuft schon eine Prüfung, gilt diese.
export function pruefen(): Promise<void> {
  if (laufend) return laufend.jetzt();
  einzeln ??= abfragen().catch(() => {}).finally(() => (einzeln = null));
  return einzeln;
}

export function verbindungenVerfolgen(): () => void {
  laufend?.stoppen();
  const dieser = takt(abfragen, TAKT_MS);
  laufend = dieser;
  return () => {
    dieser.stoppen();
    if (laufend === dieser) laufend = null;
  };
}
