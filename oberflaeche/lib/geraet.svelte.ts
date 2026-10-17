// Telefon oder Rechner: eigene Ansicht fürs Telefon (schmal, oder grob zeigend und flach im Querformat).
const ANFRAGE = "(max-width: 760px), (pointer: coarse) and (max-height: 500px)";
export const geraet = $state({ mobil: false });

export function geraetStarten(): void {
  const m = matchMedia(ANFRAGE);
  geraet.mobil = m.matches;
  m.addEventListener("change", () => (geraet.mobil = m.matches));
}
