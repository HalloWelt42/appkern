<script lang="ts">
  // Rechte Leiste einer Seite (siehe lib/leiste.svelte.ts): breit daneben, schmal als einschiebbare Tafel.
  import type { Snippet } from "svelte";
  import { leiste, leisteSchliessen } from "../lib/leiste.svelte";

  let { children }: { children: Snippet } = $props();
</script>

<svelte:window onkeydown={(e) => e.key === "Escape" && leisteSchliessen()} />

{#if leiste.offen}<button class="leiste-schleier" aria-label="Leiste schließen" onclick={leisteSchliessen}></button>{/if}
<aside class="leiste" class:offen={leiste.offen}>
  <button class="rund leiste-zu" title="Schließen" onclick={leisteSchliessen}><i class="fa-solid fa-xmark"></i></button>
  {@render children()}
</aside>
