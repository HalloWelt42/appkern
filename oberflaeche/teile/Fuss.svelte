<script lang="ts">
  // Fußleiste wie die Leitstelle: laufende Aufträge, jede Verbindung als Punkt mit Namen (schmal nur Punkte), rechts
  // was die App dort zeigt (`rechts`, etwa Modell und Kontext) und die Fassung.
  import type { Snippet } from "svelte";
  import { auftraege } from "../lib/auftraege.svelte";
  import { gehe } from "../lib/navigation.svelte";
  import { sitzung } from "../lib/sitzung.svelte";
  import { verbindungen } from "../lib/verbindungen.svelte";

  let { rechts }: { rechts?: Snippet } = $props();
  const app = $derived(sitzung.app!);
  const text = $derived(
    auftraege.laufen ? `${auftraege.laufen} ${auftraege.laufen === 1 ? "Auftrag läuft" : "Aufträge laufen"}`
      : auftraege.warten ? `${auftraege.warten} ${auftraege.warten === 1 ? "Auftrag wartet" : "Aufträge warten"}` : "keine Aufträge",
  );
</script>

<footer class="fuss">
  <button class:arbeit-laeuft={auftraege.laufen > 0} title="Aufträge ansehen" onclick={() => gehe("auftraege")}>
    <i class="fa-solid fa-gears"></i>{text}</button>
  <span class="verbindungen">
    {#each verbindungen.liste as v (v.name)}
      <span class="verbindung" class:gestoert={!v.ok} title="{v.name}{v.adresse ? ` (${v.adresse})` : ''}: {v.ok ? `verbunden, ${v.meldung}` : v.meldung}">
        <span class="punkt"></span><span class="name">{v.name}</span></span>
    {/each}
  </span>
  <span class="rechts">{@render rechts?.()}<span class="zahl-schrift" title="Fassung der App, Appkern {app.appkern}">{app.fassung}</span></span>
</footer>
