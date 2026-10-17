// Neue Fassung auf dem Server: nie ein hartes Neuladen verlangen (Muster aus Orbit und Kellerwolke).
// Die Startseite kommt ohne Zwischenspeicher, Skripte und Gestaltung tragen Prüfsummen im Namen. Meldet die App eine
// andere Fassung als die eingebaute, lädt die Seite von selbst neu: beim Start sofort, später beim nächsten
// Seitenwechsel (die Navigation meldet ihn) oder wenn das Fenster wieder nach vorn kommt; nie, solange die App etwas tut, das ein Neuladen
// abbräche (sie meldet das über `ruhig`). Dazwischen steht ein Band mit Knopf. Je Fassung nur ein selbsttätiger
// Versuch (Merker in der Sitzung), damit ein hängender Zwischenspeicher keine Schleife auslöst.
import { hole } from "./api.svelte";
import { arbeitsfrei } from "./arbeit.svelte";
import type { AppInfo } from "./typen";

const START_FENSTER_MS = 10_000;
const PRUEFEN_MS = 60_000;

export type Anlass = "start" | "takt" | "seitenwechsel" | "sichtbar";

export const fassung = $state<{ eingebaut: string; neu: string | null }>({ eingebaut: "", neu: null });

let ruhigFrage: () => boolean = () => true;
let merker = "app_neu_geladen";

export function ruhig(): boolean {
  return arbeitsfrei() && ruhigFrage();
}

function erlaubt(neu: string): boolean {
  try {
    if (sessionStorage.getItem(merker) === neu) return false;
    sessionStorage.setItem(merker, neu);
  } catch {
    // ohne Sitzungsspeicher kein Merker: dann lieber einmal laden als nie
  }
  return true;
}

export function vielleichtNeuLaden(anlass: Anlass): void {
  const neu = fassung.neu;
  if (!neu || anlass === "takt" || !ruhig()) return;
  if (anlass === "start" && performance.now() > START_FENSTER_MS) return;
  if (erlaubt(neu)) location.reload();
}

// Die Fassung, die der Server meldet, mit der eingebauten vergleichen.
export function fassungVergleichen(app: AppInfo | null, anlass: Anlass): void {
  if (!app || !fassung.eingebaut) return;
  merker = `${app.kennung}_neu_geladen`;
  // verglichen wird mit der Oberfläche, die der Server ausliefert (ältere Apps melden nur ihre eigene Fassung)
  const server = app.oberflaeche ?? app.fassung;
  fassung.neu = server !== fassung.eingebaut ? server : null;
  vielleichtNeuLaden(anlass);
}

async function pruefen(anlass: Anlass): Promise<void> {
  try {
    fassungVergleichen(await hole<AppInfo>("/app"), anlass);
  } catch {
    // ohne Verbindung meldet das der Verbindungsstand
  }
}

function sichtbar(): void {
  if (document.visibilityState === "visible") pruefen("sichtbar");
}

// `eingebaut`: die Fassung, mit der die Oberfläche gebaut wurde; `frage`: ob die App gerade neu laden darf.
export function fassungVerfolgen(eingebaut: string, frage?: () => boolean): () => void {
  fassung.eingebaut = eingebaut;
  if (frage) ruhigFrage = frage;
  const takt = setInterval(() => pruefen("takt"), PRUEFEN_MS);
  document.addEventListener("visibilitychange", sichtbar);
  return () => {
    clearInterval(takt);
    document.removeEventListener("visibilitychange", sichtbar);
  };
}
