<script lang="ts">
  // Wurzel jeder App-Oberfläche: Einrichtung, Anmeldung, dann Rechner- oder Telefonansicht.
  // Entwurf (freigegeben 17.10.2026): oberflaeche/mockups/schale.html und schale-mobil.html.
  import { onMount } from "svelte";
  import { einzelton, nurEinTon } from "../lib/wiedergabe.svelte";
  import { anzeigeStarten } from "../lib/anzeige.svelte";
  import { fassungVerfolgen } from "../lib/fassung.svelte";
  import { geraet, geraetStarten } from "../lib/geraet.svelte";
  import { navigation, navigationStarten } from "../lib/navigation.svelte";
  import { sitzung, starten } from "../lib/sitzung.svelte";
  import type { Anfrage, Bereich, EinstellungsReiter } from "../lib/typen";
  import Anmeldung from "./Anmeldung.svelte";
  import AppWeg from "./AppWeg.svelte";
  import Einrichtung from "./Einrichtung.svelte";
  import Rechner from "./Rechner.svelte";
  import MobilSchale from "./mobil/MobilSchale.svelte";

  // `fassung`: mit welcher Fassung die Oberfläche gebaut wurde (aus version.json der App); weicht die des Servers ab,
  // lädt die Seite von selbst neu. `ruhig`: ob die App gerade neu laden darf (etwa nicht während einer Aufnahme).
  // `oeffnen`: wohin eine Anfrage zum Öffnen aus der Kellerwolke führt (Weg /anfrage/<id>), etwa die Ansicht der Datei.
  // `einstellungen`: eigene Reiter der App in den Einstellungen (neben den erzeugten Gruppen).
  let { bereiche = [], fassung, ruhig, oeffnen, einstellungen = [] }: {
    bereiche?: Bereich[]; fassung: string; ruhig?: () => boolean; oeffnen?: (a: Anfrage) => Promise<string> | string;
    einstellungen?: EinstellungsReiter[] } = $props();

  anzeigeStarten();
  geraetStarten();
  // Ein Seitenwechsel beendet kurze Wiedergaben (Abschnitt, Probe); der große Spieler hält von selbst an
  $effect(() => {
    void navigation.teile.join("/");
    void navigation.seite;
    einzelton.anhalten();
  });
  onMount(() => {
    const fassungStoppen = fassungVerfolgen(fassung, ruhig);
    starten();
    const navigationStoppen = navigationStarten();
    const tonStoppen = nurEinTon();
    return () => {
      fassungStoppen();
      navigationStoppen();
      tonStoppen();
    };
  });
</script>

{#if !sitzung.geladen}
  <div class="laden">Lädt ...</div>
{:else if !sitzung.app}
  <AppWeg ganz nochmal={starten} />
{:else if sitzung.app.einrichtung_noetig}
  <Einrichtung />
{:else if !sitzung.angemeldet}
  <Anmeldung />
{:else if geraet.mobil}
  <MobilSchale bereiche={bereiche.filter((b) => b.geraete !== "rechner")} {oeffnen} {einstellungen} />
{:else}
  <Rechner bereiche={bereiche.filter((b) => b.geraete !== "telefon")} {oeffnen} {einstellungen} />
{/if}
