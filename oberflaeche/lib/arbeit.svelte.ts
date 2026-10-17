// Was die App gerade tut, das ein Neuladen (neue Fassung) abbräche: Wiedergabe, Aufnahme, Hochladen, ungespeicherte
// Änderungen. Bausteine (Spieler, Rekorder, Hochladen) melden es selbst; die Schale fragt es vor einem Neuladen ab.
export const arbeit = $state({ wiedergabe: false, aufnahme: false, hochladen: 0, ungespeichert: false });

export function arbeitsfrei(): boolean {
  return !arbeit.wiedergabe && !arbeit.aufnahme && arbeit.hochladen === 0 && !arbeit.ungespeichert;
}
