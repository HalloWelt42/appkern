// Lesen der Merkmale (Attribute) eines Instruments, an einer Stelle für Regler und Anzeigen.

/** Text eines Merkmals oder die Vorgabe */
export const attr = <T extends string | undefined>(el: Element, name: string, vorgabe: T): string | T =>
  el.hasAttribute(name) ? (el.getAttribute(name) ?? "") : vorgabe;

/** Zahl eines Merkmals oder die Vorgabe */
export const num = <T extends number | undefined>(el: Element, name: string, vorgabe: T): number | T =>
  el.hasAttribute(name) ? parseFloat(el.getAttribute(name) ?? "") : vorgabe;

/** Erklärung im Hover: die Beschriftung bleibt der übliche Fachbegriff, "hilfe" erklärt ihn (Titel und für Vorleser) */
export function hilfe(el: HTMLElement, ziel: Element = el): void {
  const text = el.getAttribute("hilfe");
  if (text === null) return;
  el.title = text;
  ziel.setAttribute("aria-description", text);
}

/** Leuchtfarbe aus dem Merkmal farbe als --farbe (Marken --led-*) */
export function leuchtfarbe(el: HTMLElement, merkmal = "farbe", marke = "--farbe"): void {
  const farbe = el.getAttribute(merkmal);
  if (farbe) el.style.setProperty(marke, `var(--led-${farbe})`);
}

/** Text für innerHTML: Merkmale stammen aus dem Markup der App, werden aber nie als HTML gedeutet */
export const sicher = (text: string): string =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
