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

export function setzeZeilenMarke(view: EditorView, zeile: number | null): void {
  view.dispatch({ effects: setzen.of(zeile) });
}
