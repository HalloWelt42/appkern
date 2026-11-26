/*
 * Haltepunkte für den Debugger: ein roter Punkt in einer eigenen Rinne links der Zeilennummern, gesetzt und gelöscht
 * mit einem Klick. Beim Tippen wandern die Punkte mit ihrer Zeile mit; jede Änderung meldet die Erweiterung mit den
 * Zeilennummern (ab 1, aufsteigend). Von außen lassen sie sich alle zusammen setzen (gemerkte, anderswo gesetzte).
 */
import { RangeSet, StateEffect, StateField, type EditorState, type Extension } from "@codemirror/state";
import { EditorView, GutterMarker, gutter } from "@codemirror/view";

class Punkt extends GutterMarker {
  toDOM(): Node {
    const punkt = document.createElement("span");
    punkt.className = "cm-haltepunkt";
    return punkt;
  }
}
const punkt = new Punkt();

/** Anfang der Zeile, deren Haltepunkt umgeschaltet wird */
const umschalten = StateEffect.define<number>();
/** Anfänge aller Zeilen mit Haltepunkt, von außen gesetzt; ersetzt die bisherigen */
const alleSetzen = StateEffect.define<number[]>();

const punkte = StateField.define<RangeSet<GutterMarker>>({
  create: () => RangeSet.empty,
  update(set, tr) {
    let neu = set.map(tr.changes);
    for (const effekt of tr.effects) {
      if (effekt.is(alleSetzen)) {
        neu = RangeSet.of(effekt.value.map((von) => punkt.range(von)), true);
        continue;
      }
      if (!effekt.is(umschalten)) continue;
      let gesetzt = false;
      neu.between(effekt.value, effekt.value, () => {
        gesetzt = true;
      });
      neu = gesetzt
        ? neu.update({ filter: (von) => von !== effekt.value })
        : neu.update({ add: [punkt.range(effekt.value)] });
    }
    return neu;
  },
});

function zeilen(state: EditorState): number[] {
  const nummern = new Set<number>();
  for (let it = state.field(punkte).iter(); it.value; it.next()) nummern.add(state.doc.lineAt(it.from).number);
  return [...nummern].sort((a, b) => a - b);
}

/** Gesetzte Haltepunkte (Zeilen ab 1, aufsteigend); ohne Rinne keine */
export function haltepunkteVon(view: EditorView): number[] {
  return view.state.field(punkte, false) ? zeilen(view.state) : [];
}

/** Setzt die Haltepunkte von außen, etwa gemerkte; die Rinne meldet danach wie nach einem Klick. Zeilen, die es im
 *  Code nicht gibt, fallen still weg. Ohne Rinne wirkt es nicht. */
export function haltepunkteSetzen(view: EditorView, nummern: readonly number[]): void {
  if (!view.state.field(punkte, false)) return;
  const doc = view.state.doc;
  const gueltig = [...new Set(nummern)].filter((z) => Number.isInteger(z) && z >= 1 && z <= doc.lines).sort((a, b) => a - b);
  view.dispatch({ effects: alleSetzen.of(gueltig.map((z) => doc.line(z).from)) });
}

const aussehen = EditorView.baseTheme({
  ".cm-haltepunkt-rinne .cm-gutterElement": { width: "16px", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" },
  ".cm-haltepunkt": { display: "block", width: "9px", height: "9px", borderRadius: "50%", background: "var(--ed-haltepunkt)" },
  ".cm-haltepunkt-rinne .cm-gutterElement:hover:empty::before": {
    content: '""', width: "9px", height: "9px", borderRadius: "50%", background: "var(--ed-haltepunkt)", opacity: "0.35",
  },
});

export function haltepunkte(beiAenderung: (zeilen: number[]) => void): Extension {
  return [
    punkte,
    gutter({
      class: "cm-haltepunkt-rinne",
      markers: (view) => view.state.field(punkte),
      initialSpacer: () => punkt,
      // auch leere Zeilen bekommen ein Feld, das beim Zeigen den Punkt andeutet
      renderEmptyElements: true,
      domEventHandlers: {
        mousedown(view, zeile) {
          view.dispatch({ effects: umschalten.of(zeile.from) });
          return true;
        },
      },
    }),
    aussehen,
    EditorView.updateListener.of((upd) => {
      // beim Einschalten (die Rinne kommt erst mit diesem Schritt dazu) fehlt das Feld im Zustand davor
      if (upd.startState.field(punkte, false) !== upd.state.field(punkte)) beiAenderung(zeilen(upd.state));
    }),
  ];
}
