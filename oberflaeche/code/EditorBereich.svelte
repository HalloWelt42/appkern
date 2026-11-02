<script lang="ts">
  // Editor für Code (CodeMirror 6, aus der Codeschmiede, WIKI-48; Ausstattung in editor/editor.ts). In beide Richtungen
  // an `code` gebunden, damit die Seite den Inhalt kennt (Prüfen, Probelauf); ändert die Seite `code` (Zurücksetzen,
  // anderes Beispiel), folgt der Editor. Mit `mitHaltepunkten` eine Rinne für Haltepunkte des Debuggers.
  import { onDestroy, onMount } from "svelte";
  import type { EditorView } from "@codemirror/view";
  import type { Funktionsbestand } from "./editor/aufrufe";
  import { bestandSetzen, erstelleEditor, haltepunkteSchalten } from "./editor/editor";
  import { werteSetzen } from "./editor/werte";
  import { setzeZeilenMarke } from "./editor/zeilenmarke";
  import type { Rahmen } from "./aufzeichnung";

  let { sprache, code = $bindable(), markierteZeile = null, befehle = [], mitHaltepunkten = false, haltepunkte = $bindable([]),
        bestand = null, werte = null }: {
    sprache: string;
    code: string;
    /** hervorgehobene Zeile (ab 1), etwa beim Abspielen eines Laufs */
    markierteZeile?: number | null;
    /** Befehle für die Vervollständigung, etwa gehe() einer Aufgabe */
    befehle?: readonly string[];
    /** Rinne für Haltepunkte des Debuggers; die gesetzten Zeilen stehen in `haltepunkte` */
    mitHaltepunkten?: boolean;
    haltepunkte?: number[];
    /** Funktionen der gewählten Fassung: unbekannte Aufrufe werden markiert, die übrigen vorgeschlagen; wechselt live */
    bestand?: Funktionsbestand | null;
    /** Rahmen des Schritts, auf dem der Debugger steht: Werte beim Überfahren eines Namens (WIKI-53) */
    werte?: readonly Rahmen[] | null;
  } = $props();

  let host: HTMLDivElement | undefined = $state();
  let view = $state.raw<EditorView | null>(null);

  onMount(() => {
    if (!host) return;
    view = erstelleEditor({
      parent: host,
      sprache,
      initialerCode: code,
      befehle,
      beiAenderung: (neuerCode) => {
        code = neuerCode;
      },
    });
  });

  // Rinne für Haltepunkte folgt `mitHaltepunkten`, auch wenn es erst nach dem Aufbau des Editors feststeht
  $effect(() => {
    if (!view) return;
    haltepunkteSchalten(view, mitHaltepunkten ? (zeilen) => (haltepunkte = zeilen) : undefined);
    if (!mitHaltepunkten) haltepunkte = [];
  });

  // ändert die Seite `code` von außen, bekommt der Editor den neuen Inhalt; nur bei echtem Unterschied, sonst käme
  // jede Änderung aus dem Editor hier noch einmal an
  $effect(() => {
    if (view && code !== view.state.doc.toString()) {
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: code } });
    }
  });

  $effect(() => {
    if (view) setzeZeilenMarke(view, markierteZeile);
  });

  $effect(() => {
    if (view) bestandSetzen(view, bestand);
  });

  $effect(() => {
    if (view) werteSetzen(view, werte);
  });

  onDestroy(() => {
    view?.destroy();
  });
</script>

<div class="code-editor" bind:this={host}></div>

<style>
  .code-editor { width: 100%; height: 100%; overflow: hidden; background: var(--ed-grund); }
  .code-editor :global(.cm-editor) { height: 100%; }
  .code-editor :global(.cm-editor.cm-focused) { outline: none; }
  .code-editor :global(.cm-zeilen-marke) { background: color-mix(in srgb, var(--akzent) 16%, transparent); }
</style>
