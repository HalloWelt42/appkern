// Die rechte Leiste einer Seite. Breit steht sie neben dem Inhalt; schmaler als 1280 Pixel wird sie eine Tafel, die
// über den Inhalt fährt (`offen`), mit Schleier und Knopf zum Schließen. Ein Ortswechsel schließt sie.
export const leiste = $state({ offen: false });

export function leisteOeffnen(): void {
  leiste.offen = true;
}

export function leisteSchliessen(): void {
  leiste.offen = false;
}
