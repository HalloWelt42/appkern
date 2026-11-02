/*
 * Funktionsbestand einer Fassung (Nachschlag WIKI-52): Aufrufe von Funktionen, die es in der gewählten Fassung einer
 * Sprache nicht gibt, werden unterstrichen, mit einem Hinweis, ab oder bis wann es sie gibt; die Vervollständigung
 * bietet die Funktionen der Fassung an. Wer den Editor nutzt, gibt den Bestand mit (welche Funktionen es gibt und was
 * zu einem Aufruf zu sagen ist); der Editor selbst kennt keine Fassungen. Erkannt werden freie Aufrufe im Syntaxbaum
 * (keine Methoden, keine Funktionen, die der Code selbst festlegt).
 */

import { completeFromList } from "@codemirror/autocomplete";
import { ensureSyntaxTree, syntaxTree } from "@codemirror/language";
import { linter, type Diagnostic } from "@codemirror/lint";
import { EditorState, type Extension } from "@codemirror/state";

export interface Funktionsbestand {
  /** Funktionen der gewählten Fassung, für die Vervollständigung */
  funktionen: readonly string[];
  /** was zu einem Aufruf zu sagen ist (Name klein geschrieben); null: in Ordnung */
  pruefe: (name: string) => string | null;
}

/** so lange nach dem letzten Tastendruck wird geprüft (wie die Syntaxprüfung) */
const PRUEFEN_NACH_MS = 400;
const ZERLEGEN_MS = 200;

function befunde(state: EditorState, bestand: Funktionsbestand): Diagnostic[] {
  const baum = ensureSyntaxTree(state, state.doc.length, ZERLEGEN_MS) ?? syntaxTree(state);
  const eigene = new Set<string>();
  const aufrufe: { name: string; from: number; to: number }[] = [];
  baum.iterate({
    enter: (k) => {
      if (k.name === "FunctionDefinition") {
        const name = k.node.getChild("Name");
        if (name) eigene.add(state.sliceDoc(name.from, name.to).toLowerCase());
      } else if (k.name === "CallExpression") {
        // frei aufgerufen: vorn ein Name ("\strlen" wie "strlen"), keine Methode, Variable oder Ausdruck
        const kopf = k.node.firstChild;
        if (kopf && (kopf.name === "Name" || kopf.name === "QualifiedName")) {
          aufrufe.push({ name: state.sliceDoc(kopf.from, kopf.to).replace(/^\\/, "").toLowerCase(), from: kopf.from, to: kopf.to });
        }
      }
    },
  });
  const liste: Diagnostic[] = [];
  for (const a of aufrufe) {
    if (eigene.has(a.name)) continue;
    const hinweis = bestand.pruefe(a.name);
    if (hinweis) liste.push({ from: a.from, to: a.to, severity: "warning", message: hinweis });
  }
  return liste;
}

export function funktionsbestand(bestand: Funktionsbestand): Extension {
  const vorschlaege = completeFromList(bestand.funktionen.map((f) => ({ label: f, type: "function", detail: "eingebaut" })));
  return [
    linter((view) => befunde(view.state, bestand), { delay: PRUEFEN_NACH_MS }),
    EditorState.languageData.of(() => [{ autocomplete: vorschlaege }]),
  ];
}
