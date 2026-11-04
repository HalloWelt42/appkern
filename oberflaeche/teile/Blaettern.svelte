<script lang="ts">
  // Blättern in einer Einzelansicht (IMG-22): zum vorigen und nächsten Eintrag der Liste, aus der man kam, mit den
  // Pfeiltasten links und rechts, Knöpfen am Rand und Wischen am Telefon. Der Inhalt (etwa das große Bild) kommt als
  // children; die Seite entscheidet, was "vorher" und "nachher" heißt (Adresse ersetzen, nachladen am Ende). Ohne
  // `onvorher` oder `onnachher` fehlt der jeweilige Knopf. Tasten zählen nicht, solange ein Eingabefeld den Fokus hat
  // oder `aktiv` aus ist (etwa während die Vollansicht offen ist, die selbst blättert). Klassen mit dem Kürzel bl-.
  import type { Snippet } from "svelte";

  let { onvorher, onnachher, stand = "", aktiv = true, children }:
    { onvorher?: () => void; onnachher?: () => void; stand?: string; aktiv?: boolean; children: Snippet } = $props();

  function tippt(ziel: EventTarget | null): boolean {
    const e = ziel as HTMLElement | null;
    return !!e && (e.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(e.tagName));
  }

  function taste(e: KeyboardEvent) {
    if (!aktiv || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || tippt(e.target)) return;
    if (e.key === "ArrowLeft" && onvorher) { e.preventDefault(); onvorher(); }
    else if (e.key === "ArrowRight" && onnachher) { e.preventDefault(); onnachher(); }
  }

  // Wischen: waagrecht mindestens 60 Pixel und deutlich mehr als senkrecht, nur mit Finger oder Stift
  let start: { x: number; y: number } | null = null;
  function runter(e: PointerEvent) {
    start = e.pointerType === "mouse" ? null : { x: e.clientX, y: e.clientY };
  }
  function hoch(e: PointerEvent) {
    if (!start) return;
    const dx = e.clientX - start.x, dy = e.clientY - start.y;
    start = null;
    if (Math.abs(dx) < 60 || Math.abs(dx) < 2 * Math.abs(dy)) return;
    if (dx < 0) onnachher?.();
    else onvorher?.();
  }
</script>

<svelte:window onkeydown={taste} />

<div class="bl" role="group" aria-label="Blättern" onpointerdown={runter} onpointerup={hoch} onpointercancel={() => (start = null)}>
  {@render children()}
  {#if onvorher}
    <button class="bl-knopf bl-vorher" title="Voriges (Pfeil links)" aria-label="Voriges" onclick={onvorher}><i class="fa-solid fa-chevron-left"></i></button>
  {/if}
  {#if onnachher}
    <button class="bl-knopf bl-nachher" title="Nächstes (Pfeil rechts)" aria-label="Nächstes" onclick={onnachher}><i class="fa-solid fa-chevron-right"></i></button>
  {/if}
  {#if stand}<span class="bl-stand">{stand}</span>{/if}
</div>

<style>
  .bl { position: relative; min-width: 0; touch-action: pan-y; }
  .bl-knopf { position: absolute; top: 50%; transform: translateY(-50%); width: 44px; height: 44px; border: 0; border-radius: var(--r3);
              display: grid; place-items: center; background: var(--flaeche); color: var(--text); box-shadow: var(--schatten); cursor: pointer;
              opacity: .85; transition: opacity var(--schnell); }
  .bl-knopf:hover, .bl-knopf:focus-visible { opacity: 1; }
  .bl-vorher { left: var(--a2); }
  .bl-nachher { right: var(--a2); }
  .bl-stand { position: absolute; right: var(--a2); bottom: var(--a2); padding: 2px 8px; border-radius: var(--r2); background: var(--flaeche);
              color: var(--text-2); font-size: var(--marke); font-family: var(--schrift-zahl); box-shadow: var(--schatten); }
</style>
