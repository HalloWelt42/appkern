/*
 * Deutsche Texte für die Bedienteile des Editors (Suchen und Ersetzen,
 * Einklappen, Vorschläge, Befunde). Schlüssel sind die Originaltexte.
 */

import { EditorState } from "@codemirror/state";

export const deutscheTexte = EditorState.phrases.of({
  Find: "Suchen",
  Replace: "Ersetzen",
  next: "weiter",
  previous: "zurück",
  all: "alle",
  "match case": "Groß und klein",
  "by word": "ganzes Wort",
  regexp: "regulärer Ausdruck",
  replace: "ersetzen",
  "replace all": "alle ersetzen",
  close: "schließen",
  "current match": "aktueller Treffer",
  "replaced $ matches": "$ Treffer ersetzt",
  "replaced match on line $": "Treffer in Zeile $ ersetzt",
  "on line": "in Zeile",
  "Go to line": "Gehe zu Zeile",
  go: "los",
  "Folded lines": "Eingeklappte Zeilen",
  "Unfolded lines": "Ausgeklappte Zeilen",
  to: "bis",
  "folded code": "eingeklappter Code",
  unfold: "ausklappen",
  "Fold line": "Zeile einklappen",
  "Unfold line": "Zeile ausklappen",
  "Control character": "Steuerzeichen",
  Completions: "Vorschläge",
  Diagnostics: "Befunde",
  "No diagnostics": "Keine Befunde",
  "Selection deleted": "Auswahl gelöscht",
});
