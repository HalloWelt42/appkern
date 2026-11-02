/*
 * Syntaxprüfung beim Tippen: der Parser der Sprache markiert Stellen,
 * die nicht zur Grammatik passen; sie werden unterstrichen und am Rand
 * markiert. Geprüft wird nur die Schreibweise, nicht, ob der Code tut,
 * was er soll; das bleibt der Prüfung.
 */

import { ensureSyntaxTree, syntaxTree } from "@codemirror/language";
import { linter, lintGutter, type Diagnostic } from "@codemirror/lint";
import type { EditorState, Extension } from "@codemirror/state";

/** so lange nach dem letzten Tastendruck wird geprüft */
const PRUEFEN_NACH_MS = 400;
/** länger darf das Zerlegen eines großen Textes nicht dauern */
const ZERLEGEN_MS = 200;

function meldung(stueck: string): string {
  if (!stueck.trim()) return "Hier fehlt etwas, etwa eine Klammer, ein Doppelpunkt oder ein Komma.";
  const kurz = stueck.length > 24 ? `${stueck.slice(0, 24)} ...` : stueck;
  return `Unerwartet an dieser Stelle: "${kurz.trim()}"`;
}

function befunde(state: EditorState): Diagnostic[] {
  const baum = ensureSyntaxTree(state, state.doc.length, ZERLEGEN_MS) ?? syntaxTree(state);
  const ende = state.doc.length;
  const liste: Diagnostic[] = [];
  baum.iterate({
    enter: (knoten) => {
      if (!knoten.type.isError) return;
      // ein leerer Fehler am Textende markiert das letzte Zeichen
      const from = knoten.from >= ende ? Math.max(0, ende - 1) : knoten.from;
      const to = Math.min(ende, Math.max(knoten.to, from + 1));
      const vorher = liste[liste.length - 1];
      // dicht aufeinanderfolgende Fehler sind meist eine Ursache
      if (vorher && from <= vorher.to + 1) {
        vorher.to = Math.max(vorher.to, to);
        return;
      }
      liste.push({ from, to, severity: "error", message: meldung(state.sliceDoc(knoten.from, knoten.to)) });
    },
  });
  return liste;
}

export const syntaxpruefung: Extension = [lintGutter(), linter((view) => befunde(view.state), { delay: PRUEFEN_NACH_MS })];
