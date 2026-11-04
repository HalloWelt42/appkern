<script lang="ts">
  // Karte (IMG-19): die eine Bauweise für Karten nebeneinander, damit Teile über alle Karten einer Reihe fluchten.
  // Von oben nach unten: optionale Bildfläche mit festem Seitenverhältnis (ohne Bild ein ruhiger Platzhalter gleicher
  // Höhe), Kopf, Angaben, Fuß. Der Fuß sitzt immer unten (margin-top: auto); data-karte und data-fuss sind fest eingebaut,
  // damit die Fluchtprüfung des Appkerns (werkzeuge/ansicht.mjs) jede Karte erfasst. In KartenRaster.svelte stellen,
  // das alle Karten einer Reihe gleich hoch macht. Mit `onwahl` ist die ganze obere Karte eine Klickfläche; Knöpfe im
  // Fuß bleiben eigene Ziele. Klassen mit dem Kürzel kb-, damit nichts mit der Schale zusammenfällt.
  import type { Snippet } from "svelte";

  let { bild = undefined, bildAlt = "", verhaeltnis = "4 / 3", symbol = "fa-image", gewaehlt = false, titel = "", onwahl,
        kopf, children, fuss, marken, flaeche }:
    { bild?: string | null; bildAlt?: string; verhaeltnis?: string; symbol?: string; gewaehlt?: boolean; titel?: string;
      onwahl?: () => void; kopf?: Snippet; children?: Snippet; fuss?: Snippet; marken?: Snippet; flaeche?: Snippet } = $props();

  // eine Bildfläche gibt es, sobald die Karte eine haben soll (bild nicht undefined oder eigener Inhalt `flaeche`, etwa
  // ein Mosaik), auch wenn das Bild selbst fehlt; ihre Höhe folgt immer dem Seitenverhältnis
  const mitFlaeche = $derived(bild !== undefined || !!flaeche);
  // in einer klickbaren Karte (button) nur Inline-Inhalt, sonst Blöcke wie Formulare und Listen
  const innen = $derived(onwahl ? "span" : "div");
</script>

<article class="kb" class:kb-gewaehlt={gewaehlt} data-karte>
  <svelte:element this={onwahl ? "button" : "div"} class="kb-oben" class:kb-klickbar={!!onwahl} title={titel || undefined}
                  onclick={onwahl} type={onwahl ? "button" : undefined} role={onwahl ? undefined : "presentation"}>
    {#if mitFlaeche}
      <svelte:element this={innen} class="kb-flaeche" style:aspect-ratio={verhaeltnis}>
        {#if flaeche}{@render flaeche()}
        {:else if bild}<img src={bild} alt={bildAlt} loading="lazy" />
        {:else}<i class="fa-solid {symbol} kb-platzhalter" aria-hidden="true"></i>{/if}
        {@render marken?.()}
      </svelte:element>
    {/if}
    {#if kopf}<svelte:element this={innen} class="kb-kopf">{@render kopf()}</svelte:element>{/if}
    {#if children}<svelte:element this={innen} class="kb-angaben">{@render children()}</svelte:element>{/if}
  </svelte:element>
  {#if fuss}<div class="kb-fuss" data-fuss>{@render fuss()}</div>{/if}
</article>

<style>
  .kb { display: flex; flex-direction: column; min-width: 0; height: 100%; background: var(--flaeche); border-radius: var(--r3);
        box-shadow: var(--schatten); overflow: hidden; }
  .kb-gewaehlt { box-shadow: 0 0 0 2px var(--akzent-flaeche), var(--schatten); }
  .kb-oben { display: flex; flex-direction: column; gap: var(--a2); flex: 1 1 auto; min-width: 0; padding: 0 0 var(--a2);
             border: 0; background: transparent; color: inherit; font: inherit; text-align: left; }
  .kb-klickbar { cursor: pointer; }
  .kb-klickbar:hover .kb-kopf { color: var(--akzent); }
  .kb-flaeche { position: relative; display: grid; place-items: center; width: 100%; overflow: hidden; background: var(--mulde); }
  .kb-flaeche img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .kb-platzhalter { font-size: var(--kennzahl); color: var(--text-3); }
  /* Kopf immer mindestens zwei Zeilen hoch, damit Angaben unter ein- und zweizeiligen Titeln auf einer Linie beginnen */
  .kb-kopf { display: flex; align-items: baseline; gap: var(--a2); padding: var(--a3) var(--a4) 0; font-weight: 600; font-size: var(--gross);
             line-height: 1.35; min-height: calc(2lh + var(--a3)); min-width: 0; overflow-wrap: anywhere; }
  .kb-angaben { display: flex; flex-direction: column; gap: 4px; padding: 0 var(--a4); font-size: var(--klein); color: var(--text-2); min-width: 0; }
  .kb-fuss { margin-top: auto; display: flex; align-items: center; gap: var(--a2); flex-wrap: wrap; padding: 0 var(--a4) var(--a3); min-height: 0; }
</style>
