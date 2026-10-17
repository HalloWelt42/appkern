<script lang="ts">
  // Wurzel jeder App-Oberfläche: Einrichtung, Anmeldung, dann Rechner- oder Telefonansicht.
  // Entwurf (freigegeben 17.10.2026): oberflaeche/mockups/schale.html und schale-mobil.html.
  import { onMount } from "svelte";
  import { anzeigeStarten } from "../lib/anzeige.svelte";
  import { fassungVerfolgen } from "../lib/fassung.svelte";
  import { geraet, geraetStarten } from "../lib/geraet.svelte";
  import { navigationStarten } from "../lib/navigation.svelte";
  import { sitzung, starten } from "../lib/sitzung.svelte";
  import type { Bereich } from "../lib/typen";
  import Anmeldung from "./Anmeldung.svelte";
  import Einrichtung from "./Einrichtung.svelte";
  import Rechner from "./Rechner.svelte";
  import MobilSchale from "./mobil/MobilSchale.svelte";

  // `fassung`: mit welcher Fassung die Oberfläche gebaut wurde (aus version.json der App); weicht die des Servers ab,
  // lädt die Seite von selbst neu. `ruhig`: ob die App gerade neu laden darf (etwa nicht während einer Aufnahme).
  let { bereiche = [], fassung, ruhig }: { bereiche?: Bereich[]; fassung: string; ruhig?: () => boolean } = $props();

  anzeigeStarten();
  geraetStarten();
  onMount(() => {
    const fassungStoppen = fassungVerfolgen(fassung, ruhig);
    starten();
    const navigationStoppen = navigationStarten();
    return () => {
      fassungStoppen();
      navigationStoppen();
    };
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
