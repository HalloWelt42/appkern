// Anzeige auf diesem Gerät: Thema und eingeklappte Seitenleiste, gemerkt im Browser. Welches Thema gilt, bis der Mensch
// wählt, gibt die App der Schale mit (`ansicht`); ohne Angabe wie das System. Die Schrift ist fest (stil/schale.css).
export type Thema = "hell" | "dunkel" | "system";
export interface AnzeigeVorgabe {
  thema?: Thema;
}

export const THEMEN: [Thema, string][] = [["dunkel", "Dunkel"], ["hell", "Hell"], ["system", "wie das System"]];

const SCHLUESSEL = "appkern_anzeige";
export const anzeige = $state<{ thema: Thema; eingeklappt: boolean }>({ thema: "system", eingeklappt: false });

function dunkel(): boolean {
  return anzeige.thema === "dunkel" || (anzeige.thema === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
}

function anwenden(): void {
  document.documentElement.dataset.theme = dunkel() ? "dunkel" : "hell";
}

export function anzeigeStarten(vorgabe: AnzeigeVorgabe = {}): void {
  Object.assign(anzeige, vorgabe);
  try {
    const gemerkt = JSON.parse(localStorage.getItem(SCHLUESSEL) ?? "{}");
    if (THEMEN.some(([t]) => t === gemerkt.thema)) anzeige.thema = gemerkt.thema;
    if (typeof gemerkt.eingeklappt === "boolean") anzeige.eingeklappt = gemerkt.eingeklappt;
  } catch {
    // Vorgabe bleibt
  }
  anwenden();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", anwenden);
}

export function anzeigeSetzen(wert: Partial<{ thema: Thema; eingeklappt: boolean }>): void {
  Object.assign(anzeige, wert);
  try {
    localStorage.setItem(SCHLUESSEL, JSON.stringify(anzeige));    // eine früher gemerkte Schriftstufe fällt dabei weg
  } catch {
    // gilt dann nur bis zum Neuladen
  }
  anwenden();
}
