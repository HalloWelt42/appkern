/*
 * Vervollständigung im Editor: nur einzelne Befehle, keine mehrzeiligen
 * Bausteine. Die Vorschläge der Sprache (Schlüsselwörter, eingebaute
 * Namen, eigene Namen im Code, CSS-Eigenschaften und -Werte, SQL-Wörter)
 * bleiben; aus Gerüsten wie einer ganzen Schleife oder Funktion wird
 * das einzelne Wort (for, def), den Rest schreibt man selbst. Python
 * bringt seine Schlüsselwörter nur als Gerüste mit, die übrigen stehen
 * hier.
 *
 * Dazu kommen die Befehle einer Aufgabe, etwa gehe() und links() im
 * Roboter-Parcours.
 */

import {
  autocompletion,
  completeFromList,
  type Completion,
  type CompletionContext,
  type CompletionResult,
  type CompletionSource,
} from "@codemirror/autocomplete";
import { pythonLanguage } from "@codemirror/lang-python";
import type { Extension } from "@codemirror/state";

type Sprachquelle = CompletionSource | readonly (string | Completion)[];

const PYTHON_WOERTER = [
  "and", "as", "assert", "async", "await", "break", "case", "continue", "del", "elif", "else", "except",
  "finally", "global", "in", "is", "lambda", "match", "nonlocal", "not", "or", "pass", "raise", "return",
  "while", "with", "yield",
].map((w) => ({ label: w, type: "keyword" }));

/** Ein Vorschlag fügt höchstens eine Zeile ein; aus einem Gerüst wird sein Wort */
function einzeilig(o: Completion): Completion {
  const geruest = typeof o.apply === "function" || (typeof o.apply === "string" && o.apply.includes("\n"));
  return geruest ? { label: o.label, type: o.type ?? "keyword" } : o;
}

/** je Wort nur ein Vorschlag (aus "if" und "if / else" wird ein "if") */
function einmalig(optionen: Completion[]): Completion[] {
  const gesehen = new Set<string>();
  return optionen.filter((o) => !gesehen.has(o.label) && gesehen.add(o.label));
}

async function sprachVorschlaege(context: CompletionContext): Promise<CompletionResult | null> {
  const quellen = context.state.languageDataAt<Sprachquelle>("autocomplete", context.pos);
  const ergebnisse = await Promise.all(
    quellen.map((q) => (typeof q === "function" ? q(context) : completeFromList(q)(context))),
  );
  const treffer = ergebnisse
    .filter((e): e is CompletionResult => e !== null)
    .map((e) => ({ ...e, options: e.options.map(einzeilig) }))
    .filter((e) => e.options.length > 0);
  if (!treffer.length) return null;
  // Quellen beginnen ihr Wort verschieden weit vorn; es gilt das kürzeste Stück vor dem Cursor
  const von = Math.max(...treffer.map((e) => e.from));
  const passend = treffer.filter((e) => e.from === von);
  return { from: von, options: einmalig(passend.flatMap((e) => e.options)) };
}

/** Vervollständigung mit den Befehlen der Aufgabe dazu */
export function vervollstaendigung(befehle: readonly string[] = []): Extension {
  const quellen: CompletionSource[] = [sprachVorschlaege];
  if (befehle.length) {
    quellen.push(completeFromList(befehle.map((b) => ({ label: b, type: "function", detail: "Befehl", boost: 10 }))));
  }
  return [
    autocompletion({ override: quellen, icons: false }),
    pythonLanguage.data.of({ autocomplete: PYTHON_WOERTER }),
  ];
}
