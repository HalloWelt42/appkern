<script lang="ts">
  // Kopf: Marke mit Rolle, Verbindungen und laufende Aufträge.
  import { auftraege } from "../lib/auftraege.svelte";
  import { gehe } from "../lib/navigation.svelte";
  import { sitzung } from "../lib/sitzung.svelte";
  import { verbindungen } from "../lib/verbindungen.svelte";

  const app = $derived(sitzung.app!);
  const auftragsText = $derived(
    [auftraege.laufen ? `${auftraege.laufen} ${auftraege.laufen === 1 ? "läuft" : "laufen"}` : "",
     auftraege.warten ? `${auftraege.warten} ${auftraege.warten === 1 ? "wartet" : "warten"}` : ""]
      .filter(Boolean)
      .join(", "),
  );
</script>

<header class="kopf">
  <div class="marke"><span class="symbol"><i class="fa-solid {app.symbol}"></i></span> {app.name}</div>
  <span class="rolle" title="Leitstelle verteilt Aufträge, Kellerwolke hält die Dateien, {app.name} {app.rolle}">
    <i class="fa-solid fa-wave-square"></i>{app.rolle}
  </span>
  <div class="kopf-rechts">
    {#each verbindungen.liste as v (v.name)}
      <span class="pille" class:warn={!v.ok} title="{v.adresse || v.name}: {v.meldung}"><span class="punkt"></span>{v.name}</span>
    {/each}
    {#if auftragsText}
      <button class="pille aktiv" style="border:0; cursor:pointer" onclick={() => gehe("auftraege")}>
        <i class="fa-solid fa-gears"></i>{auftragsText}
      </button>
    {/if}
  </div>
</header>
