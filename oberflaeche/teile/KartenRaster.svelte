<script lang="ts">
  // Raster für Karten (IMG-19): Spalten mit einer Mindestbreite, alle Karten einer Reihe gleich hoch (align-items: stretch),
  // damit Bildfläche, Kopf und Fuß über die Reihe fluchten. Am Telefon eine Spalte.
  import type { Snippet } from "svelte";

  let { breite = "260px", children }: { breite?: string; children: Snippet } = $props();
</script>

<div class="kr" style:--kr-breite={breite}>{@render children()}</div>

<style>
  .kr { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(var(--kr-breite), 100%), 1fr)); gap: var(--a4); align-items: stretch; }
</style>
