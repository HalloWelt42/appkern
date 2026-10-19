<script lang="ts">
  // Ansicht am Rechner: Kopf, Band bei fehlender Verbindung, Navigation, Seite (Aufträge mit Leiste).
  import { onMount } from "svelte";
  import AnfrageOeffnen from "./AnfrageOeffnen.svelte";
  import { verfolgen } from "../lib/auftraege.svelte";
  import { fassung, ruhig } from "../lib/fassung.svelte";
  import { navigation } from "../lib/navigation.svelte";
  import type { Anfrage, Bereich, EinstellungsReiter } from "../lib/typen";
  import { verbindungen, verbindungenVerfolgen } from "../lib/verbindungen.svelte";
  import Auftraege from "./Auftraege.svelte";
  import Band from "./Band.svelte";
  import Einstellungen from "./Einstellungen.svelte";
  import Kopf from "./Kopf.svelte";
  import Navigation from "./Navigation.svelte";
  import Protokoll from "./Protokoll.svelte";

  let { bereiche, oeffnen, einstellungen = [] }: { bereiche: Bereich[]; oeffnen?: (a: Anfrage) => Promise<string> | string;
                                                 einstellungen?: EinstellungsReiter[] } = $props();

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
  const fehlend = $derived(verbindungen.liste.filter((v) => !v.ok));
</script>

<div class="fenster-voll">
  <Kopf />
  {#if fassung.neu}
    <div class="band">
      <i class="fa-solid fa-rotate"></i>
      <span><b>Neue Fassung {fassung.neu} ist da.</b>
        {ruhig() ? "Beim nächsten Seitenwechsel lädt die App sie von selbst." : "Sie lädt von selbst, sobald die laufende Arbeit hier fertig ist."}</span>
      <button class="knopf" onclick={() => location.reload()}><i class="fa-solid fa-rotate"></i> Jetzt neu laden</button>
    </div>
  {:else if fehlend.length}<Band verbindungen={fehlend} />{:else}<div></div>{/if}
  <div class="geruest" class:mit-leiste={!bereich && seite === "auftraege"}>
    <Navigation {bereiche} {seite} />
    {#if bereich}
      <section class="seite"><bereich.seite /></section>
    {:else if seite === "anfrage" && oeffnen}
      <section class="seite"><AnfrageOeffnen {oeffnen} /></section>
    {:else if seite === "protokoll"}
      <Protokoll />
    {:else if seite === "einstellungen"}
      <Einstellungen reiter={einstellungen} />
    {:else}
      <Auftraege />
    {/if}
  </div>
</div>
