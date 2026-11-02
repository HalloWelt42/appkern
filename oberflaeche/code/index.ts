// Bausteine für Code (WIKI-48, aus der Codeschmiede): Editor, Debugger und Speicherbild, dazu die Sitzung und die
// Steuerung des Debuggers und die Typen einer Aufzeichnung. Eigener Eingang (appkern-oberflaeche/code), damit Apps ohne
// Code kein CodeMirror laden. Farben aus den Marken (Abschnitt Editor in marken.css); die App lädt die Marken.
export { default as EditorBereich } from "./EditorBereich.svelte";
export { default as DebuggerBereich } from "./DebuggerBereich.svelte";
export { default as Speicherbild } from "./Speicherbild.svelte";
export { DebugSitzung, type Aufzeichner } from "./debugger/sitzung.svelte";
export { aufrufstapel, istEintritt, istHalt, istRueckkehr, springe, start, tiefe, type Stapeleintrag, type Ziel } from "./debugger/steuerung";
export { erstelleEditor, haltepunkteSchalten, SPRACHEN, type EditorOptionen, type Sprache } from "./editor/editor";
export { setzeZeilenMarke } from "./editor/zeilenmarke";
export type { Aufzeichnung, Debuglauf, Rahmen, Schritt, Wert } from "./aufzeichnung";
