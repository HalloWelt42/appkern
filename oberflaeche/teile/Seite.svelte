<script lang="ts">
  // Seitenkopf, der stehen bleibt (IMG-16, Regel "Kopf sticky, Rollfelder"): Suche, Filter, Kennzahlen und Bedienknöpfe
  // stehen im Kopf; der Inhalt darunter rollt im vorhandenen Rollfeld der Seite unter ihm durch. Der Kopf klebt oben am
  // Rollfeld (position: sticky), daher geht das in jedem Behälter und jeder Breite ohne eigenes Rollfeld. Am Telefon
  // (bis 600 Pixel) rollt wie bisher die Telefonschale mit allem. data-seitenkopf ist fest eingebaut; die Ansichtsprüfung
  // des Appkerns meldet Köpfe, Suchfelder und Filter, die beim Rollen wegrollen. `rand` ist der seitliche Innenabstand
  // des Rollfelds, damit die Fläche des Kopfs bis an dessen Ränder reicht. Klassen mit dem Kürzel sb-.
  import type { Snippet } from "svelte";

  let { kopf, children, rand = "var(--a5)" }: { kopf: Snippet; children?: Snippet; rand?: string } = $props();
</script>

<header class="sb-kopf" data-seitenkopf style:--sb-rand={rand}>{@render kopf()}</header>
{@render children?.()}

<style>
  .sb-kopf { position: sticky; top: 0; z-index: 5; display: flex; flex-direction: column; gap: var(--a3); min-width: 0;
             margin: 0 calc(-1 * var(--sb-rand)) var(--a3); padding: var(--a3) var(--sb-rand); background: var(--hg);
             box-shadow: 0 1px 0 var(--rand); }
  @media (max-width: 600px) {
    .sb-kopf { position: static; box-shadow: none; padding-top: var(--a2); padding-bottom: 0; }
  }
</style>
