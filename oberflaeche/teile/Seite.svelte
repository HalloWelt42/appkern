<script lang="ts">
  // Seite mit stehendem Kopf (IMG-16, Regel "Kopf sticky, Rollfelder"): Titel, Suche, Filter, Kennzahlen und Bedienknöpfe
  // stehen im Kopf, nur der Inhalt darunter rollt in seinem eigenen Rollfeld. Die Seite rollt nie als Ganzes. Am Telefon
  // (bis 600 Pixel) rollt wie bisher die Telefonschale; der Kopf steht dann einfach oben im Inhalt. data-seitenkopf und
  // data-rollfeld sind fest eingebaut; die Ansichtsprüfung des Appkerns meldet einen Kopf, der beim Rollen wegrollt.
  // Klassen mit dem Kürzel sb-, damit nichts mit der Schale zusammenfällt.
  import type { Snippet } from "svelte";

  let { kopf, children, rollfeld = $bindable() }: { kopf?: Snippet; children: Snippet; rollfeld?: HTMLDivElement } = $props();
</script>

<div class="sb">
  {#if kopf}<header class="sb-kopf" data-seitenkopf>{@render kopf()}</header>{/if}
  <div class="sb-rollfeld" data-rollfeld bind:this={rollfeld}>{@render children()}</div>
</div>

<style>
  .sb { flex: 1; min-height: 0; height: 100%; display: flex; flex-direction: column; min-width: 0; }
  .sb-kopf { flex: none; display: flex; flex-direction: column; gap: var(--a3); padding: var(--a4) var(--a5) var(--a3); min-width: 0;
             box-shadow: 0 1px 0 var(--rand); }
  .sb-rollfeld { flex: 1; min-height: 0; overflow-y: auto; overflow-x: clip; padding: var(--a4) var(--a5) var(--a5); min-width: 0; }
  @media (max-width: 600px) {
    .sb { height: auto; display: block; }
    .sb-kopf { padding: var(--a3) 0; box-shadow: none; }
    .sb-rollfeld { overflow: visible; padding: 0 0 var(--a4); }
  }
</style>
