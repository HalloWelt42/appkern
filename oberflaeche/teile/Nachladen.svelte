<script lang="ts">
  // Nachladen beim Rollen (IMG-16): steht am Ende einer seitenweise geladenen Liste. Kommt es in Sicht (auch in einem
  // Rollfeld der Schale), holt es über `onmehr` die nächste Seite; der Server bleibt seitenweise. Zeigt den Stand
  // ("1.240 von 5.486 geladen"), während des Ladens einen Hinweis und bei einem Fehler "Erneut versuchen". Der Knopf
  // "Weitere laden" bleibt für Tastatur und den Fall, dass ein Rollen nichts auslöst. Klassen mit dem Kürzel nl-.
  let { geladen, gesamt = null, laedt = false, fehler = "", onmehr, einheit = "geladen" }:
    { geladen: number; gesamt?: number | null; laedt?: boolean; fehler?: string; onmehr: () => void; einheit?: string } = $props();

  const zahl = (n: number) => n.toLocaleString("de-DE");
  const mehr = $derived(gesamt === null || geladen < gesamt);
  let ende = $state<HTMLDivElement>();

  // in Sicht: nachladen, solange es mehr gibt, nicht gerade geladen wird und kein Fehler steht. Nach jedem Laden neu
  // beobachten: ein Beobachter meldet nur Wechsel, ein Ende, das nach dem Laden noch in Sicht ist, sonst nie wieder
  $effect(() => {
    void geladen;
    void laedt;
    if (!ende) return;
    const beobachter = new IntersectionObserver((e) => {
      if (e.some((x) => x.isIntersecting) && mehr && !laedt && !fehler) onmehr();
    }, { rootMargin: "600px 0px" });
    beobachter.observe(ende);
    return () => beobachter.disconnect();
  });
</script>

<div class="nl" bind:this={ende} aria-live="polite">
  {#if fehler}
    <span class="nl-fehler"><i class="fa-solid fa-triangle-exclamation"></i>{fehler}</span>
    <button class="knopf klein" onclick={onmehr}><i class="fa-solid fa-rotate"></i>Erneut versuchen</button>
  {:else if laedt}
    <span class="nl-stand"><i class="fa-solid fa-spinner fa-spin"></i>Lädt weitere …</span>
  {:else if mehr}
    <span class="nl-stand">{zahl(geladen)}{gesamt !== null ? ` von ${zahl(gesamt)}` : ""} {einheit}</span>
    <button class="knopf klein still" onclick={onmehr}>Weitere laden</button>
  {:else if geladen}
    <span class="nl-stand">Alle {zahl(geladen)} {einheit}</span>
  {/if}
</div>

<style>
  .nl { display: flex; align-items: center; justify-content: center; gap: var(--a3); flex-wrap: wrap; min-height: var(--knopf-hoehe);
        padding: var(--a3) 0; font-size: var(--klein); color: var(--text-3); }
  .nl-stand { display: inline-flex; align-items: center; gap: var(--a2); font-variant-numeric: tabular-nums; }
  .nl-fehler { display: inline-flex; align-items: center; gap: var(--a2); color: var(--gefahr); }
</style>
