<script lang="ts">
  // Kopf: Marke mit Fassung und Rolle; rechts eine Pille für alle Verbindungen (gestörte mit Namen, Einzelheiten in
  // der Fußleiste) und was die App selbst dort zeigt (`rechts`, etwa eine Glocke). Antwortet die App selbst nicht,
  // steht dort nur das: ihre Verbindungen wären dann ein alter Stand.
  import type { Snippet } from "svelte";
  import { pruefen, verbindung } from "../lib/erreichbar.svelte";
  import { sitzung } from "../lib/sitzung.svelte";
  import { verbindungen } from "../lib/verbindungen.svelte";
  import { fest } from "../lib/stelle.svelte";

  let { rechts }: { rechts?: Snippet } = $props();
  const app = $derived(sitzung.app!);
  const gestoert = $derived(verbindungen.liste.filter((v) => !v.ok));
  const alle = $derived(verbindungen.liste.map((v) => `${v.name}: ${v.ok ? "verbunden" : v.meldung}`).join("\n"));
</script>

<header class="kopf" use:fest={"oben"}>
  <div class="marke"><span class="symbol"><i class="fa-solid {app.symbol}"></i></span> {app.name}
    <span class="marke-fassung" title="Fassung der App">{app.fassung}</span></div>
  <span class="rolle" title="Leitstelle verteilt Aufträge, Kellerwolke hält die Dateien, {app.name} {app.rolle}">
    <i class="fa-solid fa-wave-square"></i>{app.rolle}
  </span>
  <div class="kopf-rechts">
    {#if !verbindung.ok}
      <button class="pille warn" style="border:0; cursor:pointer" title="Erneut versuchen" onclick={() => pruefen()}>
        <span class="punkt"></span>{verbindung.meldung}</button>
    {:else if verbindungen.geprueft}
      {#if gestoert.length}
        <span class="pille warn" title={alle}><span class="punkt"></span>{gestoert.length === 1 ? `${gestoert[0].name} gestört`
          : `${gestoert.length} von ${verbindungen.liste.length} gestört`}</span>
      {:else}
        <span class="pille" title={alle}><span class="punkt"></span>alles verbunden</span>
      {/if}
    {/if}
    {@render rechts?.()}
  </div>
</header>
