<script lang="ts">
  // Wurzel jeder App-Oberfläche: Einrichtung, Anmeldung, dann Rechner- oder Telefonansicht.
  // Entwurf (freigegeben 17.10.2026): oberflaeche/mockups/schale.html und schale-mobil.html.
  import { onMount } from "svelte";
  import { anzeigeStarten } from "../lib/anzeige.svelte";
  import { geraet, geraetStarten } from "../lib/geraet.svelte";
  import { navigationStarten } from "../lib/navigation.svelte";
  import { sitzung, starten } from "../lib/sitzung.svelte";
  import type { Bereich } from "../lib/typen";
  import Anmeldung from "./Anmeldung.svelte";
  import Einrichtung from "./Einrichtung.svelte";
  import Rechner from "./Rechner.svelte";
  import MobilSchale from "./mobil/MobilSchale.svelte";

  let { bereiche = [] }: { bereiche?: Bereich[] } = $props();

  anzeigeStarten();
  geraetStarten();
  onMount(() => {
    starten();
    return navigationStarten();
  });
</script>

{#if !sitzung.geladen}
  <div class="laden">Lädt ...</div>
{:else if !sitzung.app}
  <div class="laden">Die App antwortet gerade nicht.</div>
{:else if sitzung.app.einrichtung_noetig}
  <Einrichtung />
{:else if !sitzung.angemeldet}
  <Anmeldung />
{:else if geraet.mobil}
  <MobilSchale {bereiche} />
{:else}
  <Rechner {bereiche} />
{/if}
