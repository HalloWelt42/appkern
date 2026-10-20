<script lang="ts">
  // Wurzel jeder App-Oberfläche: Einrichtung, Anmeldung, dann Rechner- oder Telefonansicht.
  // Entwurf (freigegeben 17.10.2026): oberflaeche/mockups/schale.html und schale-mobil.html.
  import { onMount, untrack } from "svelte";
  import { einzelton, nurEinTon } from "../lib/wiedergabe.svelte";
  import { anzeigeStarten, type AnzeigeVorgabe } from "../lib/anzeige.svelte";
  import type { Snippet } from "svelte";
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
  // `ansicht`: das Thema, bis der Mensch in diesem Browser wählt. `kopf`, `navigation`, `fuss`: eigene
  // Teile der App in Kopf (rechts), Seitenleiste (unter den Bereichen) und Fußleiste am Rechner.
  let { bereiche = [], fassung, ruhig, oeffnen, einstellungen = [], ansicht = {}, kopf, navigation: navZusatz, fuss }: {
    bereiche?: Bereich[]; fassung: string; ruhig?: () => boolean; oeffnen?: (a: Anfrage) => Promise<string> | string;
    einstellungen?: EinstellungsReiter[]; ansicht?: AnzeigeVorgabe; kopf?: Snippet; navigation?: Snippet; fuss?: Snippet } = $props();

  anzeigeStarten(untrack(() => ansicht));     // nur die Vorgabe beim Start; danach gilt die Wahl im Browser
  // Flächenfarbe des Symbols aus der App-Angabe (Kopf, Anmeldung)
  $effect(() => {
    const farbe = sitzung.app?.farbe;
    if (farbe) {
      document.documentElement.style.setProperty("--app-farbe", farbe);
      document.documentElement.style.setProperty("--app-farbe-tief", `color-mix(in srgb, ${farbe} 72%, #000)`);
      document.documentElement.style.setProperty("--symbol-flaeche", `linear-gradient(135deg, ${farbe}, color-mix(in srgb, ${farbe} 72%, #000))`);
    }
  });
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
  <Rechner bereiche={bereiche.filter((b) => b.geraete !== "telefon")} {oeffnen} {einstellungen} {kopf} navigation={navZusatz} {fuss} />
{/if}
