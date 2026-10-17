// Verbindungen der App (Kellerwolke, Leitstelle), regelmäßig geprüft.
import { hole } from "./api.svelte";
import type { Verbindung } from "./typen";

const TAKT_MS = 30000;
export const verbindungen = $state<{ liste: Verbindung[]; geprueft: boolean }>({ liste: [], geprueft: false });

export async function pruefen(): Promise<void> {
  try {
    verbindungen.liste = await hole<Verbindung[]>("/verbindungen");
  } catch {
    // die App selbst ist weg; das zeigt der Verbindungsstand der Anfragen
  } finally {
    verbindungen.geprueft = true;
  }
}

export function verbindungenVerfolgen(): () => void {
  pruefen();
  const takt = setInterval(pruefen, TAKT_MS);
  return () => clearInterval(takt);
}
