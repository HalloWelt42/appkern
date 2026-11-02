/*
 * Editor für Code (CodeMirror 6, aus der Codeschmiede, WIKI-48): liefert eine EditorView, die eine Svelte-Komponente
 * in ein Element einhängt. Die Sprache wählt die Grammatik; eine unbekannte Sprache bleibt einfacher Text.
 *
 * Ausstattung wie in einer Entwicklungsumgebung: Farbschema (das klassische, dunkel und hell, aus den Marken),
 * Vervollständigung einzelner Befehle, Syntaxprüfung beim Tippen (nur in Programmiersprachen), Klammern schließen und
 * markieren, Suchen und Ersetzen, Mehrfachauswahl, deutsche Bedientexte; auf Wunsch Haltepunkte für den Debugger.
 */

import { closeBrackets, closeBracketsKeymap, completionKeymap } from "@codemirror/autocomplete";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { css } from "@codemirror/lang-css";
import { html } from "@codemirror/lang-html";
import { javascript } from "@codemirror/lang-javascript";
import { markdown } from "@codemirror/lang-markdown";
import { php } from "@codemirror/lang-php";
import { python } from "@codemirror/lang-python";
import { sql } from "@codemirror/lang-sql";
import { bracketMatching, foldGutter, foldKeymap, indentOnInput, indentUnit } from "@codemirror/language";
import { lintKeymap } from "@codemirror/lint";
import { highlightSelectionMatches, searchKeymap } from "@codemirror/search";
import { Compartment, EditorState } from "@codemirror/state";
import {
  crosshairCursor,
  drawSelection,
  dropCursor,
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
  rectangularSelection,
} from "@codemirror/view";

import { funktionsbestand, type Funktionsbestand } from "./aufrufe";
import { haltepunkte } from "./haltepunkte";
import { deutscheTexte } from "./phrasen";
import { klassischesSchema } from "./schema";
import { syntaxpruefung } from "./syntaxpruefung";
import { vervollstaendigung } from "./vervollstaendigung";
import { zeilenMarke } from "./zeilenmarke";

const SPRACHEN_EXTENSIONS = {
  // Python und PHP rücken üblicherweise um vier Leerzeichen ein
  python: () => [python(), indentUnit.of("    ")],
  javascript: () => javascript(),
  // PHP mit HTML drumherum, wie Beispiele aus Handbüchern mit <?php beginnen
  php: () => [php(), indentUnit.of("    ")],
  html: () => html(),
  css: () => css(),
  sql: () => sql(),
  markdown: () => markdown(),
};

export type Sprache = keyof typeof SPRACHEN_EXTENSIONS;
/** Sprachen mit eigener Grammatik im Editor */
export const SPRACHEN = Object.keys(SPRACHEN_EXTENSIONS) as Sprache[];

/** Sprachen mit Grammatik, deren Schreibweise beim Tippen geprüft wird */
const MIT_SYNTAXPRUEFUNG: ReadonlySet<string> = new Set(["python", "javascript", "php", "html", "css", "sql"]);

function spracheExtension(sprache: string) {
  const factory = SPRACHEN_EXTENSIONS[sprache as Sprache];
  return factory ? factory() : [];
}

export interface EditorOptionen {
  parent: HTMLElement;
  sprache: string;
  initialerCode: string;
  beiAenderung: (code: string) => void;
  /** Befehle der Aufgabe für die Vervollständigung, etwa gehe() */
  befehle?: readonly string[];
  /** gesetzt: Rinne für Haltepunkte des Debuggers, meldet jede Änderung */
  beiHaltepunkten?: (zeilen: number[]) => void;
}

// Die Rinne für Haltepunkte lässt sich zu- und abschalten: ob eine Aufgabe einen Debugger hat, steht oft erst fest,
// wenn der Editor schon steht (vorher fehlte die Rinne dann ganz)
const haltepunktRinne = new Compartment();

export function haltepunkteSchalten(view: EditorView, beiHaltepunkten?: (zeilen: number[]) => void): void {
  view.dispatch({ effects: haltepunktRinne.reconfigure(beiHaltepunkten ? haltepunkte(beiHaltepunkten) : []) });
}

// Der Funktionsbestand der gewählten Fassung wechselt mit ihr, während der Editor steht (WIKI-52)
const bestandFach = new Compartment();

export function bestandSetzen(view: EditorView, bestand: Funktionsbestand | null): void {
  view.dispatch({ effects: bestandFach.reconfigure(bestand ? funktionsbestand(bestand) : []) });
}

export function erstelleEditor(opts: EditorOptionen): EditorView {
  const state = EditorState.create({
    doc: opts.initialerCode,
    extensions: [
      haltepunktRinne.of(opts.beiHaltepunkten ? haltepunkte(opts.beiHaltepunkten) : []),
      bestandFach.of([]),
      lineNumbers(),
      highlightActiveLineGutter(),
      foldGutter(),
      highlightActiveLine(),
      drawSelection(),
      dropCursor(),
      EditorState.allowMultipleSelections.of(true),
      rectangularSelection(),
      crosshairCursor(),
      indentOnInput(),
      bracketMatching(),
      closeBrackets(),
      highlightSelectionMatches(),
      history(),
      keymap.of([
        ...closeBracketsKeymap,
        ...defaultKeymap,
        ...searchKeymap,
        ...historyKeymap,
        ...foldKeymap,
        ...completionKeymap,
        ...lintKeymap,
        indentWithTab,
      ]),
      spracheExtension(opts.sprache),
      vervollstaendigung(opts.befehle),
      MIT_SYNTAXPRUEFUNG.has(opts.sprache) ? syntaxpruefung : [],
      klassischesSchema,
      deutscheTexte,
      zeilenMarke,
      EditorView.lineWrapping,
      EditorView.updateListener.of((upd) => {
        if (upd.docChanged) {
          opts.beiAenderung(upd.state.doc.toString());
        }
      }),
    ],
  });

  return new EditorView({ state, parent: opts.parent });
}
