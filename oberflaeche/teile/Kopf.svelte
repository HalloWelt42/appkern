<script lang="ts">
  // Kopf: Marke mit Fassung und Rolle; rechts eine Pille für alle Verbindungen (gestörte mit Namen, Einzelheiten in
  // der Fußleiste) und was die App selbst dort zeigt (`rechts`, etwa eine Glocke). Antwortet die App selbst nicht,
  // steht dort nur das: ihre Verbindungen wären dann ein alter Stand. `mitte`: was die App in die Mitte stellt (etwa
  // ihre Suche); dann entfällt die Rolle neben der Marke.
  import type { Snippet } from "svelte";
  import { pruefen, verbindung } from "../lib/erreichbar.svelte";
  import { sitzung } from "../lib/sitzung.svelte";
  import AppSymbol from "./AppSymbol.svelte";
  import { gestoert as istGestoert, verbindungen, vermisst } from "../lib/verbindungen.svelte";
  import Vermisst from "./Vermisst.svelte";
  import { fest } from "../lib/stelle.svelte";

  let { rechts, mitte }: { rechts?: Snippet; mitte?: Snippet } = $props();
  const app = $derived(sitzung.app!);
  // die Pille nennt nur gestörte; vermisste (nie eingetragen) zeigt das Minisymbol daneben (WIKI-68)
  const gestoert = $derived(verbindungen.liste.filter(istGestoert));
  const eingerichtet = $derived(verbindungen.liste.filter((v) => !vermisst(v)));
  const alle = $derived(verbindungen.liste.map((v) => `${v.name}: ${v.ok ? "verbunden" : v.meldung}`).join("\n"));
</script>

<header class="kopf" use:fest={"oben"}>
  <div class="marke"><AppSymbol {app} /> {app.name}
    <span class="marke-fassung" title="Fassung der App">{app.fassung}</span></div>
  {#if mitte}
    <div class="kopf-mitte">{@render mitte()}</div>
  {:else}
    <span class="rolle" title="Leitstelle verteilt Aufträge, Kellerwolke hält die Dateien, {app.name} {app.rolle}">
      <i class="fa-solid fa-wave-square"></i>{app.rolle}
    </span>
  {/if}
  <div class="kopf-rechts">
    {#if !verbindung.ok}
      <button class="pille warn" style="border:0; cursor:pointer" title="Erneut versuchen" onclick={() => pruefen()}>
        <span class="punkt"></span>{verbindung.meldung}</button>
    {:else if verbindungen.geprueft}
      {#if gestoert.length}
        <span class="pille warn" title={alle}><span class="punkt"></span>{gestoert.length === 1 ? `${gestoert[0].name} gestört`
          : `${gestoert.length} von ${eingerichtet.length} gestört`}</span>
      {:else if verbindungen.liste.length && eingerichtet.length === verbindungen.liste.length}
        <span class="pille" title={alle}><span class="punkt"></span>alles verbunden</span>
      {/if}
    {/if}
    <Vermisst />
    {@render rechts?.()}
  </div>
</header>
