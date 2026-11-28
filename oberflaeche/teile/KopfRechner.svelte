<script lang="ts">
  // Ansicht am Rechner in der Form "kopf" (KINO-2): Kopf mit Pillen-Navigation, Band (App antwortet nicht, neue Fassung
  // oder fehlende Verbindung), Seite, unten was die App dort zeigt (`fuss`, etwa eine Spieler- oder Betriebsleiste). Die
  // Navigation ragt in den Inhalt; die Seite rollt nie selbst, nur ihre Felder.
  import { onMount, type Snippet } from "svelte";
  import AnfrageOeffnen from "./AnfrageOeffnen.svelte";
  import AppWeg from "./AppWeg.svelte";
  import { verbindung } from "../lib/erreichbar.svelte";
  import { verfolgen } from "../lib/auftraege.svelte";
  import { fassung, ruhig } from "../lib/fassung.svelte";
  import { navigation } from "../lib/navigation.svelte";
  import type { Anfrage, Bereich, EinstellungsReiter } from "../lib/typen";
  import { gestoert, verbindungen, verbindungenVerfolgen } from "../lib/verbindungen.svelte";
  import Auftraege from "./Auftraege.svelte";
  import Band from "./Band.svelte";
  import Einstellungen from "./Einstellungen.svelte";
  import Kopfleiste from "./Kopfleiste.svelte";
  import Protokoll from "./Protokoll.svelte";

  let { bereiche, oeffnen, einstellungen = [], kopf, fuss, schriftzug, unterzeile, praegung, auftraegeTitel }: {
    bereiche: Bereich[]; oeffnen?: (a: Anfrage) => Promise<string> | string; einstellungen?: EinstellungsReiter[];
    kopf?: Snippet; fuss?: Snippet; schriftzug?: string; unterzeile?: string; praegung?: "silber" | "gold"; auftraegeTitel?: string } = $props();

  onMount(() => {
    const auftraegeStoppen = verfolgen();
    const verbindungenStoppen = verbindungenVerfolgen();
    return () => {
      auftraegeStoppen();
      verbindungenStoppen();
    };
  });

  const seite = $derived(navigation.seite || bereiche[0]?.schluessel || "auftraege");
  const bereich = $derived(bereiche.find((b) => b.schluessel === seite));
  const fehlend = $derived(verbindungen.liste.filter(gestoert));
</script>

<div class="fenster-voll ak-kopfschale">
  <Kopfleiste {bereiche} {seite} {schriftzug} {unterzeile} {praegung} {auftraegeTitel} rechts={kopf} />
  {#if !verbindung.ok}
    <AppWeg />
  {:else if fassung.neu}
    <div class="band">
      <i class="fa-solid fa-rotate"></i>
      <span><b>Neue Fassung {fassung.neu} ist da.</b>
        {ruhig() ? "Beim nächsten Seitenwechsel lädt die App sie von selbst." : "Sie lädt von selbst, sobald die laufende Arbeit hier fertig ist."}</span>
      <button class="knopf" onclick={() => location.reload()}><i class="fa-solid fa-rotate"></i> Jetzt neu laden</button>
    </div>
  {:else if fehlend.length}<Band verbindungen={fehlend} />{:else}<div></div>{/if}
  <main class="ak-kopfschale-mitte">
    {#if bereich}
      <section class="seite"><bereich.seite /></section>
    {:else if seite === "anfrage" && oeffnen}
      <section class="seite"><AnfrageOeffnen {oeffnen} /></section>
    {:else if seite === "protokoll"}
      <Protokoll />
    {:else if seite === "einstellungen"}
      <Einstellungen reiter={einstellungen} />
    {:else}
      <Auftraege titel={auftraegeTitel} />
    {/if}
  </main>
  {#if fuss}<div class="ak-kopfschale-fuss">{@render fuss()}</div>{/if}
</div>
