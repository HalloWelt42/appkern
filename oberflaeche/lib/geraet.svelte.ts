// Telefon oder Rechner: eigene Ansicht fürs Telefon. Mit Maus (feiner Zeiger) erst bis 600 Pixel Breite, damit ein
// schmales Fenster oder eine vergrößerte Seite am Rechner die Rechneransicht behält; mit dem Finger (grober Zeiger)
// wie bisher bis 760 Pixel, und flach im Querformat.
const ANFRAGE = "(max-width: 600px), (pointer: coarse) and (max-width: 760px), (pointer: coarse) and (max-height: 500px)";
export const geraet = $state({ mobil: false });

export function geraetStarten(): void {
  const m = matchMedia(ANFRAGE);
  geraet.mobil = m.matches;
  m.addEventListener("change", () => (geraet.mobil = m.matches));
}
