<script lang="ts">
  // Lautsprecher zum Vorlesen: liest `text` über den Weg der App (Vorgabe `/vorlesen` aus `appkern.vorlesen`, der die
  // App Vorlesen ruft) mit dem Vorleser vor; ein zweites Tippen hält an. Solange der erste Satz noch kommt, dreht sich
  // das Zeichen. `text` darf eine Funktion sein, dann wird der Text erst im Tippen gebaut. Mit `beschriftung` steht
  // ein Wort neben dem Zeichen (sonst nur das Zeichen mit Hinweis beim Überfahren); es bleibt beim Lesen stehen, nur das
  // Zeichen wechselt zu Anhalten, damit der Knopf seine Breite behält. Ist keine App Vorlesen eingetragen
  // (`vorlesbar.da` falsch), zeigt der Knopf sich nicht; eine App mit eigenem Weg setzt `immer`.
  import { onMount } from "svelte";
  import { vorlesbar, vorlesbarPruefen, vorleser } from "../lib/vorlesen.svelte";

  let { kennung, text, pfad = "/vorlesen", daten = {}, titel = "Vorlesen", beschriftung = "", klein = false,
        immer = false }: {
    kennung: string; text: string | (() => string); pfad?: string; daten?: Record<string, unknown>; titel?: string;
    beschriftung?: string; klein?: boolean; immer?: boolean;
  } = $props();

  const liest = $derived(vorleser.kennung === kennung);
  const wartet = $derived(liest && vorleser.wartet);
  const hinweis = $derived(liest ? "Vorlesen anhalten" : titel);

  onMount(() => {
    if (!immer) void vorlesbarPruefen();
  });

  function tippen(): void {
    const inhalt = typeof text === "function" ? text() : text;
    if (!liest && !inhalt.trim()) return;
    vorleser.umschalten(kennung, pfad, { ...daten, text: inhalt });
  }
</script>

{#if immer || vorlesbar.da}
  <button type="button" class="knopf {beschriftung ? '' : 'symbol ohne'}" class:klein aria-pressed={liest} title={hinweis}
          aria-label={hinweis} onclick={tippen}>
    <i class="fa-solid {wartet ? 'fa-spinner fa-spin' : liest ? 'fa-stop' : 'fa-volume-high'}"></i>{beschriftung}
  </button>
{/if}
