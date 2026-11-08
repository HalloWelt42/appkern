<script lang="ts">
  // Minisymbol für vermisste Verbindungen (nie eingetragen, WIKI-68): statt eines Bands nur ein Warnzeichen im Kopf;
  // die Namen stehen im Hinweis, ein Tipp führt zu den Einstellungen, wo sie eingetragen werden.
  import { gehe } from "../lib/navigation.svelte";
  import { verbindungen, vermisst } from "../lib/verbindungen.svelte";

  const liste = $derived(verbindungen.liste.filter(vermisst));
  const text = $derived(`Nicht eingerichtet: ${liste.map((v) => v.name).join(", ")}. Zu den Einstellungen`);
</script>

{#if liste.length}
  <button class="vermisst" title={text} aria-label={text} onclick={() => gehe("einstellungen")}>
    <i class="fa-solid fa-triangle-exclamation"></i><span>{liste.length}</span></button>
{/if}
