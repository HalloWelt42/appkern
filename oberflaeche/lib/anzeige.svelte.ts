// Anzeige auf diesem Gerät: Thema, eingeklappte Seitenleiste und (nur für Apps, die Schriftstufen anbieten) die Stufe
// der Schrift, gemerkt im Browser. Welches Thema gilt, bis der Mensch wählt, gibt die App der Schale mit (`ansicht`);
// ohne Angabe wie das System. Die Schrift der Schale mit Seitenleiste ist fest (stil/schale.css, Stufe dicht); eine App
// mit dem Kopf (Schale `form="kopf"`, KINO-2) gibt eine Vorgabe der Stufe mit und bietet die Wahl im Kopf an.
export type Thema = "hell" | "dunkel" | "system";
export type Schriftstufe = "mittel" | "gross" | "sehr-gross";
export interface AnzeigeVorgabe {
  thema?: Thema;
  /** Schriftstufen anbieten, mit dieser Vorgabe; ohne Angabe bleibt die feste Schrift der Schale */
  schrift?: Schriftstufe;
}

export const THEMEN: [Thema, string][] = [["dunkel", "Dunkel"], ["hell", "Hell"], ["system", "wie das System"]];
/** wählbare Stufen, kleinste zuerst (die Stufen selbst stehen in stil/marken.css) */
export const SCHRIFTSTUFEN: [Schriftstufe, string][] = [["mittel", "Normal"], ["gross", "Groß"], ["sehr-gross", "Sehr groß"]];

const SCHLUESSEL = "appkern_anzeige";
export const anzeige = $state<{ thema: Thema; eingeklappt: boolean; schrift: Schriftstufe | null }>({ thema: "system", eingeklappt: false, schrift: null });

function dunkel(): boolean {
  return anzeige.thema === "dunkel" || (anzeige.thema === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
}

function anwenden(): void {
  document.documentElement.dataset.theme = dunkel() ? "dunkel" : "hell";
  if (anzeige.schrift) document.documentElement.dataset.schrift = anzeige.schrift;
}

export function anzeigeStarten(vorgabe: AnzeigeVorgabe = {}): void {
  Object.assign(anzeige, vorgabe);
  try {
    const gemerkt = JSON.parse(localStorage.getItem(SCHLUESSEL) ?? "{}");
    if (THEMEN.some(([t]) => t === gemerkt.thema)) anzeige.thema = gemerkt.thema;
    if (typeof gemerkt.eingeklappt === "boolean") anzeige.eingeklappt = gemerkt.eingeklappt;
    // eine gemerkte Stufe gilt nur, wenn die App Stufen anbietet (sonst bleibt die feste Schrift)
    if (anzeige.schrift && SCHRIFTSTUFEN.some(([s]) => s === gemerkt.schrift)) anzeige.schrift = gemerkt.schrift;
  } catch {
    // Vorgabe bleibt
  }
  anwenden();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", anwenden);
}

/** eine Stufe größer (+1) oder kleiner (-1); am Rand bleibt sie stehen */
export function schriftSchritt(richtung: 1 | -1): void {
  const i = SCHRIFTSTUFEN.findIndex(([s]) => s === anzeige.schrift);
  const neu = SCHRIFTSTUFEN[Math.min(SCHRIFTSTUFEN.length - 1, Math.max(0, i + richtung))];
  if (anzeige.schrift && neu) anzeigeSetzen({ schrift: neu[0] });
}

export function anzeigeSetzen(wert: Partial<{ thema: Thema; eingeklappt: boolean; schrift: Schriftstufe }>): void {
  Object.assign(anzeige, wert);
  try {
    localStorage.setItem(SCHLUESSEL, JSON.stringify(anzeige));    // eine früher gemerkte Schriftstufe fällt dabei weg
  } catch {
    // gilt dann nur bis zum Neuladen
  }
  anwenden();
}
