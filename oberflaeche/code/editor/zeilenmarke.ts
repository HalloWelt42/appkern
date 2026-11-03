/*
 * Hebt eine Zeile im Editor hervor, etwa die Zeile, deren Befehl der
 * Roboter gerade ausführt. Die Komponente setzt sie mit setzeZeilenMarke;
 * null nimmt die Markierung weg.
 */
import { StateEffect, StateField } from "@codemirror/state";
import { Decoration, EditorView, type DecorationSet } from "@codemirror/view";

const setzen = StateEffect.define<number | null>();
const markiert = Decoration.line({ class: "cm-zeilen-marke" });

export const zeilenMarke = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(marken, tr) {
    let neu = marken.map(tr.changes);
    for (const effekt of tr.effects) {
      if (!effekt.is(setzen)) continue;
      const zeile = effekt.value;
      neu = zeile && zeile <= tr.state.doc.lines
        ? Decoration.set([markiert.range(tr.state.doc.line(zeile).from)])
        : Decoration.none;
    }
    return neu;
  },
  provide: (feld) => EditorView.decorations.from(feld),
});

// Eine gesetzte Zeile rollt zugleich in die Mitte des Editors, damit sie zu sehen ist (Schritte im Debugger, Sprung
// aus einer Gliederung).
export function setzeZeilenMarke(view: EditorView, zeile: number | null): void {
  const gueltig = zeile !== null && zeile >= 1 && zeile <= view.state.doc.lines;
  view.dispatch({
    effects: gueltig ? [setzen.of(zeile), EditorView.scrollIntoView(view.state.doc.line(zeile).from, { y: "center" })] : setzen.of(zeile),
  });
}
