/*
 * Farbschema des Editors: das klassische Schema einer verbreiteten Entwicklungsumgebung (ältere Fassung), dunkel und
 * hell. Die Farben stehen als Marken im Abschnitt Editor von marken.css (--ed-*) und folgen dem Thema der App; hier
 * steht nur, welches Teil welche Farbe trägt. Schlüsselwörter sind fett.
 *
 * Eigenschaftsnamen bedeuten in CSS etwas anderes als in Python und JavaScript (dort Attribute eines Objekts); deshalb
 * gilt für CSS ein eigener Satz, die allgemeinen Farben gelten überall sonst.
 */

import { cssLanguage } from "@codemirror/lang-css";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import type { Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { tags as t, type Highlighter } from "@lezer/highlight";

/** Farben als Verweise auf die Marken (Abschnitt Editor) */
const FARBE = {
  grund: "var(--ed-grund)",
  text: "var(--ed-text)",
  rand: "var(--ed-rand)",
  zeilennummer: "var(--ed-nr)",
  aktiveZeile: "var(--ed-zeile)",
  auswahl: "var(--ed-auswahl)",
  cursor: "var(--ed-cursor)",
  flaeche: "var(--ed-flaeche)",
  linie: "var(--ed-linie)",
  schluessel: "var(--ed-kw)",
  zeichenkette: "var(--ed-str)",
  zahl: "var(--ed-zahl)",
  kommentar: "var(--ed-kom)",
  dokukommentar: "var(--ed-dokukom)",
  funktion: "var(--ed-fn)",
  feld: "var(--ed-feld)",
  dekorator: "var(--ed-dekorator)",
  marke: "var(--ed-marke)",
  attribut: "var(--ed-attribut)",
  wert: "var(--ed-wert)",
  verweis: "var(--ed-verweis)",
  fehler: "var(--ed-fehler)",
  warnung: "var(--ed-warnung)",
  klammer: "var(--ed-klammer)",
  klammerText: "var(--ed-klammer-text)",
  treffer: "var(--ed-treffer)",
} as const;

const F = FARBE;

const rahmen = EditorView.theme(
  {
    "&": { color: F.text, backgroundColor: F.grund, height: "100%" },
    // jedes Zeichen so, wie es getippt ist: keine Ligaturen wie -> als Pfeil
    ".cm-scroller": {
      fontFamily: "var(--schrift-code)", fontSize: "var(--klein)", lineHeight: "1.55", fontVariantLigatures: "none",
    },
    ".cm-content": { caretColor: F.cursor, padding: "var(--a3) 0" },
    ".cm-cursor, .cm-dropCursor": { borderLeftColor: F.cursor },
    "&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection":
      { backgroundColor: F.auswahl },
    ".cm-gutters": { backgroundColor: F.rand, color: F.zeilennummer, border: "none" },
    ".cm-activeLine": { backgroundColor: F.aktiveZeile },
    ".cm-activeLineGutter": { backgroundColor: F.aktiveZeile, color: F.cursor },
    "&.cm-focused .cm-matchingBracket": { backgroundColor: F.klammer, color: F.klammerText, outline: "none" },
    "&.cm-focused .cm-nonmatchingBracket": { color: F.fehler, backgroundColor: "transparent" },
    ".cm-selectionMatch": { backgroundColor: F.treffer },
    ".cm-searchMatch": { backgroundColor: F.treffer, outline: `1px solid ${F.wert}` },
    ".cm-searchMatch.cm-searchMatch-selected": { backgroundColor: F.auswahl },
    ".cm-foldPlaceholder": { backgroundColor: F.flaeche, color: F.text, border: "none", padding: "0 4px" },
    ".cm-tooltip": { backgroundColor: F.flaeche, border: `1px solid ${F.linie}`, color: F.text },
    ".cm-tooltip-autocomplete > ul": { fontFamily: "var(--schrift-code)", fontSize: "var(--klein)" },
    ".cm-tooltip-autocomplete > ul > li": { padding: "2px 8px" },
    ".cm-tooltip-autocomplete > ul > li[aria-selected]": { backgroundColor: F.auswahl, color: F.text },
    ".cm-completionMatchedText": { textDecoration: "none", color: F.funktion },
    ".cm-completionDetail": { color: F.zeilennummer, fontStyle: "normal" },
    // Wert beim Überfahren, während der Debugger auf einem Schritt steht (werte.ts)
    ".cm-wert": { padding: "6px 10px", maxWidth: "min(460px, 80vw)", fontSize: "var(--klein)" },
    ".cm-wert-kopf": { display: "flex", gap: "10px", alignItems: "baseline", marginBottom: "3px", fontFamily: "var(--schrift)" },
    ".cm-wert-kopf b": { fontFamily: "var(--schrift-code)", color: F.funktion },
    ".cm-wert-kopf span": { color: F.zeilennummer },
    ".cm-wert-inhalt": { fontFamily: "var(--schrift-code)", whiteSpace: "pre-wrap", overflowWrap: "anywhere" },
    ".cm-wert-zeilen": { display: "grid", gridTemplateColumns: "auto minmax(0, 1fr)", columnGap: "12px", fontFamily: "var(--schrift-code)" },
    ".cm-wert-zeilen > span": { overflowWrap: "anywhere" },
    ".cm-wert-zeilen > span:nth-child(odd)": { color: F.zeilennummer, textAlign: "right" },
    ".cm-wert-rest": { marginTop: "3px", color: F.zeilennummer, fontFamily: "var(--schrift)" },
    ".cm-diagnostic": { fontFamily: "var(--schrift)", fontSize: "var(--klein)" },
    ".cm-diagnostic-error": { borderLeft: `4px solid ${F.fehler}` },
    ".cm-diagnostic-warning": { borderLeft: `4px solid ${F.warnung}` },
    ".cm-lint-marker": { width: "0.9em", height: "0.9em" },
    // Bedienteile der Suchleiste im Schema des Editors, auch die Ankreuzfelder
    ".cm-panels": { backgroundColor: F.flaeche, color: F.text, colorScheme: "var(--ed-schema)" },
    ".cm-panels.cm-panels-bottom": { borderTop: `1px solid ${F.linie}` },
    ".cm-panels.cm-panels-top": { borderBottom: `1px solid ${F.linie}` },
    ".cm-panel input[type=text], .cm-textfield": {
      backgroundColor: F.grund, color: F.text, border: `1px solid ${F.linie}`, borderRadius: "0",
    },
    ".cm-panel button, .cm-button": {
      backgroundColor: F.rand, backgroundImage: "none", color: F.text, border: `1px solid ${F.linie}`, borderRadius: "0",
    },
    ".cm-panel label": { color: F.text },
  },
);

/** Farben für alle Sprachen außer CSS */
const allgemein = HighlightStyle.define([
  {
    tag: [t.keyword, t.controlKeyword, t.definitionKeyword, t.moduleKeyword, t.operatorKeyword, t.modifier, t.self, t.bool, t.null],
    color: F.schluessel,
    fontWeight: "bold",
  },
  { tag: [t.separator, t.escape, t.typeName], color: F.schluessel },
  { tag: [t.string, t.special(t.string), t.regexp], color: F.zeichenkette },
  { tag: [t.number, t.character], color: F.zahl },
  { tag: [t.lineComment, t.blockComment, t.comment], color: F.kommentar },
  { tag: t.docComment, color: F.dokukommentar, fontStyle: "italic" },
  { tag: [t.function(t.definition(t.variableName)), t.function(t.definition(t.propertyName)), t.standard(t.name)], color: F.funktion },
  { tag: [t.propertyName, t.definition(t.propertyName)], color: F.feld },
  { tag: t.function(t.propertyName), color: F.text },
  { tag: [t.meta, t.annotation], color: F.dekorator },
  { tag: [t.tagName, t.angleBracket], color: F.marke },
  { tag: t.attributeName, color: F.attribut },
  { tag: t.attributeValue, color: F.wert },
  { tag: t.heading, color: F.schluessel, fontWeight: "bold" },
  { tag: t.strong, fontWeight: "bold" },
  { tag: t.emphasis, fontStyle: "italic" },
  { tag: [t.link, t.url], color: F.verweis },
  { tag: t.monospace, color: F.wert },
  { tag: t.quote, color: F.dokukommentar },
  { tag: t.invalid, color: F.fehler },
]);

/** Farben in CSS: Selektoren, Eigenschaften und Werte */
const cssFarben = HighlightStyle.define(
  [
    { tag: [t.keyword, t.definitionKeyword, t.modifier], color: F.schluessel, fontWeight: "bold" },
    { tag: [t.separator, t.punctuation], color: F.schluessel },
    { tag: t.tagName, color: F.marke },
    { tag: [t.className, t.labelName, t.constant(t.className), t.operatorKeyword], color: F.funktion },
    { tag: t.propertyName, color: F.attribut },
    { tag: [t.atom, t.color], color: F.wert },
    { tag: [t.number, t.unit], color: F.zahl },
    { tag: t.string, color: F.zeichenkette },
    { tag: t.variableName, color: F.feld },
    { tag: [t.blockComment, t.comment], color: F.kommentar },
    { tag: t.invalid, color: F.fehler },
  ],
  { scope: cssLanguage },
);

// allgemeine Farben nur außerhalb von CSS, auch in eingebettetem CSS
const ausserhalbCss: Highlighter = {
  style: (tags) => allgemein.style(tags),
  scope: (typ) => !cssFarben.scope?.(typ),
};

export const klassischesSchema: Extension = [
  rahmen,
  syntaxHighlighting(cssFarben),
  syntaxHighlighting(ausserhalbCss),
  allgemein.module ? EditorView.styleModule.of(allgemein.module) : [],
];
