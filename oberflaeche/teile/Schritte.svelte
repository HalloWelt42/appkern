<script lang="ts">
  // Phasen eines Auftrags als Schrittkette.
  import { phasenStand } from "../lib/auftraege.svelte";
  import type { Auftrag } from "../lib/typen";

  let { auftrag }: { auftrag: Auftrag } = $props();
  const stand = $derived(phasenStand(auftrag));
  const SYMBOL = { fertig: "fa-check", fehler: "fa-xmark" } as const;
</script>

{#if auftrag.phasen.length}
  <div class="schritte">
    {#each auftrag.phasen as p, i (p.schluessel)}
      {#if i}<span class="linie"></span>{/if}
      <span class="schritt {stand[i]}">
        {#if stand[i] === "fertig" || stand[i] === "fehler"}<i class="fa-solid {SYMBOL[stand[i]]}"></i>
        {:else if p.symbol}<i class="fa-solid fa-{p.symbol}"></i>{/if}{p.titel}
      </span>
    {/each}
  </div>
{/if}
