// Anzeige auf diesem Gerät: Schriftstufe, Thema und eingeklappte Seitenleiste, gemerkt im Browser. Was gilt, bis der
// Mensch wählt, gibt die App der Schale mit (`ansicht`); ohne Angabe Mittel und wie das System.
export type Schrift = "dicht" | "normal" | "gross" | "sehr_gross";
export type Thema = "hell" | "dunkel" | "system";
export interface AnzeigeVorgabe {
  schrift?: Schrift;
  thema?: Thema;
}

// Namen der Stufen für die Oberfläche (Schlüssel bleiben technisch; "normal" heißt Mittel)
export const SCHRIFTEN: [Schrift, string][] = [["dicht", "Dicht"], ["normal", "Mittel"], ["gross", "Groß"], ["sehr_gross", "Sehr groß"]];
export const THEMEN: [Thema, string][] = [["dunkel", "Dunkel"], ["hell", "Hell"], ["system", "wie das System"]];

const SCHLUESSEL = "appkern_anzeige";
export const anzeige = $state<{ schrift: Schrift; thema: Thema; eingeklappt: boolean }>(
  { schrift: "normal", thema: "system", eingeklappt: false });

function dunkel(): boolean {
  return anzeige.thema === "dunkel" || (anzeige.thema === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
}

function anwenden(): void {
  document.documentElement.dataset.schrift = anzeige.schrift;
  document.documentElement.dataset.theme = dunkel() ? "dunkel" : "hell";
}

export function anzeigeStarten(vorgabe: AnzeigeVorgabe = {}): void {
  Object.assign(anzeige, vorgabe);
  try {
    const gemerkt = JSON.parse(localStorage.getItem(SCHLUESSEL) ?? "{}");
    if (SCHRIFTEN.some(([s]) => s === gemerkt.schrift)) anzeige.schrift = gemerkt.schrift;
    if (THEMEN.some(([t]) => t === gemerkt.thema)) anzeige.thema = gemerkt.thema;
    if (typeof gemerkt.eingeklappt === "boolean") anzeige.eingeklappt = gemerkt.eingeklappt;
  } catch {
    // Vorgabe bleibt
  }
  anwenden();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", anwenden);
}

export function anzeigeSetzen(wert: Partial<{ schrift: Schrift; thema: Thema; eingeklappt: boolean }>): void {
  Object.assign(anzeige, wert);
  try {
    localStorage.setItem(SCHLUESSEL, JSON.stringify(anzeige));
  } catch {
    // gilt dann nur bis zum Neuladen
  }
  anwenden();
}
