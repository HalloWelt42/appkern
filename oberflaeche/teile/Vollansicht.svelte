<script lang="ts">
  // Vollansicht eines Bildes (IMG-15): eine Ebene über der App, das Bild so groß, wie der Schirm erlaubt. Ein Klick aufs
  // Bild wechselt zur Originalgröße (Pixel für Pixel, rollbar), noch ein Klick zurück. Escape, "Schließen" oder ein Klick
  // neben das Bild schließen. Gibt die Ansicht mehrere Bilder mit, blättern Pfeiltasten, Wischen und die Knöpfe an der
  // Seite. Am Telefon richtet sich die Ebene nach dem Rahmen (--rahmen-sicher-oben), nie nach eigenen Zahlen.
  // Klassen tragen das Kürzel va-, damit nichts mit der Schale zusammenfällt.
  import type { VollansichtBild } from "../lib/typen";

  let { bilder, index = $bindable(0), onschliessen }:
    { bilder: VollansichtBild[]; index?: number; onschliessen: () => void } = $props();

  const bild = $derived(bilder[Math.min(Math.max(index, 0), bilder.length - 1)]);
  const mehrere = $derived(bilder.length > 1);
  let original = $state(false);
  let schliessen = $state<HTMLButtonElement>();
  $effect(() => schliessen?.focus());

  function blaettern(schritt: number) {
    if (!mehrere) return;
    index = (index + schritt + bilder.length) % bilder.length;
    original = false;
  }

  function taste(e: KeyboardEvent) {
    if (e.key === "Escape") { e.preventDefault(); onschliessen(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); blaettern(1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); blaettern(-1); }
  }

  // Wischen: waagrecht mindestens 50 Pixel und deutlich mehr als senkrecht; in Originalgröße rollt der Finger das Bild.
  // Nach einem Wischen gilt der folgende Klick nicht als Wechsel zur Originalgröße.
  let start: { x: number; y: number } | null = null;
  let gewischt = false;
  function runter(e: PointerEvent) {
    gewischt = false;
    if (e.pointerType !== "mouse") start = { x: e.clientX, y: e.clientY };
  }
  function hoch(e: PointerEvent) {
    if (!start || original) { start = null; return; }
    const dx = e.clientX - start.x, dy = e.clientY - start.y;
    start = null;
    if (Math.abs(dx) > 50 && Math.abs(dx) > 2 * Math.abs(dy)) {
      gewischt = true;
      blaettern(dx < 0 ? 1 : -1);
    }
  }
  function bildKlick() {
    if (gewischt) { gewischt = false; return; }
    original = !original;
  }
</script>

<svelte:window onkeydown={taste} />

{#if bild}
  <div class="va" class:va-original={original} role="dialog" aria-modal="true" aria-label="Bild in voller Größe">
    <button class="va-schleier" aria-label="Schließen" onclick={onschliessen}></button>
    <div class="va-fenster">
      <button class="va-bild" title={original ? "Auf Schirmgröße" : "Originalgröße"} onpointerdown={runter} onpointerup={hoch} onclick={bildKlick}>
        <img src={bild.adresse} alt={bild.alt ?? ""} width={bild.breite} height={bild.hoehe} />
      </button>
      {#if mehrere}
        <button class="va-blaettern va-zurueck" title="Voriges Bild (Pfeil links)" aria-label="Voriges Bild" onclick={() => blaettern(-1)}>
          <i class="fa-solid fa-chevron-left"></i></button>
        <button class="va-blaettern va-weiter" title="Nächstes Bild (Pfeil rechts)" aria-label="Nächstes Bild" onclick={() => blaettern(1)}>
          <i class="fa-solid fa-chevron-right"></i></button>
      {/if}
    </div>
    <div class="va-leiste">
      {#if bild.titel}<span class="va-titel">{bild.titel}</span>{/if}
      {#if bild.breite && bild.hoehe}<span class="va-masse">{bild.breite} × {bild.hoehe}</span>{/if}
      {#if mehrere}<span class="va-masse">{index + 1} von {bilder.length}</span>{/if}
      <button class="knopf klein" onclick={() => (original = !original)}>
        <i class="fa-solid {original ? 'fa-compress' : 'fa-expand'}"></i>{original ? "Auf Schirmgröße" : "Originalgröße"}</button>
      <button class="knopf klein" bind:this={schliessen} onclick={onschliessen}><i class="fa-solid fa-xmark"></i>Schließen</button>
    </div>
  </div>
{/if}

<style>
  .va { position: fixed; inset: 0; z-index: 80; display: grid; grid-template-rows: minmax(0, 1fr) auto;
        padding: calc(var(--rahmen-sicher-oben, 0px) + var(--a4)) var(--a4) var(--a3); }
  .va-schleier { position: absolute; inset: 0; border: 0; padding: 0; cursor: zoom-out;
                 background: color-mix(in srgb, var(--schattenfarbe) 92%, transparent); }
  /* Fenster und Leiste lassen Klicks daneben zum Schleier durch (schließt); nur Bild und Knöpfe fangen sie */
  .va-fenster { position: relative; min-height: 0; display: grid; place-items: center; overflow: hidden; pointer-events: none; }
  .va-original .va-fenster { overflow: auto; place-items: start center; pointer-events: auto; }
  .va-fenster > button, .va-leiste > button { pointer-events: auto; }
  .va-bild { border: 0; padding: 0; background: transparent; cursor: zoom-in; touch-action: pan-y; display: grid; place-items: center; max-width: 100%; max-height: 100%; }
  .va-original .va-bild { cursor: zoom-out; max-width: none; max-height: none; }
  .va-bild img { display: block; max-width: 100%; max-height: calc(100dvh - 140px); width: auto; height: auto; object-fit: contain; }
  .va-original .va-bild img { max-width: none; max-height: none; }
  .va-blaettern { position: absolute; top: 50%; translate: 0 -50%; width: 48px; height: 48px; border: 0; border-radius: 50%; cursor: pointer;
                  display: grid; place-items: center; background: color-mix(in srgb, var(--flaeche) 80%, transparent); color: var(--text);
                  box-shadow: var(--schatten); }
  .va-zurueck { left: var(--a2); }
  .va-weiter { right: var(--a2); }
  .va-leiste { position: relative; pointer-events: none; display: flex; gap: var(--a2); justify-content: center; align-items: center; padding-top: var(--a3); flex-wrap: wrap; }
  .va-titel { color: var(--auf-farbe); font-weight: 600; max-width: 60ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .va-masse { font-family: var(--schrift-zahl); font-size: var(--klein); color: var(--auf-farbe); }
</style>
