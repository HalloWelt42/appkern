<script lang="ts">
  // Ansicht am Rechner: Kopf, Band bei fehlender Verbindung, Navigation, Seite (Aufträge mit Leiste).
  import { onMount } from "svelte";
  import { verfolgen } from "../lib/auftraege.svelte";
  import { navigation } from "../lib/navigation.svelte";
  import type { Bereich } from "../lib/typen";
  import { verbindungen, verbindungenVerfolgen } from "../lib/verbindungen.svelte";
  import Auftraege from "./Auftraege.svelte";
  import Band from "./Band.svelte";
  import Einstellungen from "./Einstellungen.svelte";
  import Kopf from "./Kopf.svelte";
  import Navigation from "./Navigation.svelte";
  import Protokoll from "./Protokoll.svelte";

  let { bereiche }: { bereiche: Bereich[] } = $props();

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
  {#if fehlend.length}<Band verbindungen={fehlend} />{:else}<div></div>{/if}
  <div class="geruest" class:mit-leiste={!bereich && seite === "auftraege"}>
    <Navigation {bereiche} {seite} />
    {#if bereich}
      <section class="seite"><bereich.seite /></section>
    {:else if seite === "protokoll"}
      <Protokoll />
    {:else if seite === "einstellungen"}
      <Einstellungen />
    {:else}
      <Auftraege />
    {/if}
  </div>
</div>
