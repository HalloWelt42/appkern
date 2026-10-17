// Anzeige auf diesem Gerät: Schriftgröße und Thema, gemerkt im Browser.
export type Schrift = "normal" | "gross" | "sehr_gross";
export type Thema = "hell" | "dunkel" | "system";

const SCHLUESSEL = "appkern_anzeige";
export const anzeige = $state<{ schrift: Schrift; thema: Thema }>({ schrift: "normal", thema: "system" });

function dunkel(): boolean {
  return anzeige.thema === "dunkel" || (anzeige.thema === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
}

function anwenden(): void {
  document.documentElement.dataset.schrift = anzeige.schrift;
  document.documentElement.dataset.theme = dunkel() ? "dunkel" : "hell";
}

export function anzeigeStarten(): void {
  try {
    Object.assign(anzeige, JSON.parse(localStorage.getItem(SCHLUESSEL) ?? "{}"));
  } catch {
    // Vorgabe bleibt
  }
  anwenden();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", anwenden);
}

export function anzeigeSetzen(wert: Partial<{ schrift: Schrift; thema: Thema }>): void {
  Object.assign(anzeige, wert);
  try {
    localStorage.setItem(SCHLUESSEL, JSON.stringify(anzeige));
  } catch {
    // gilt dann nur bis zum Neuladen
  }
  anwenden();
}
