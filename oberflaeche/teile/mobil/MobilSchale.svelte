<script lang="ts">
  // Eigene Ansicht fürs Telefon: Reiter unten (Bereiche der App, Aufträge, Mehr), Band bei fehlender Verbindung.
  // Höhe, Kopf, Fußleiste und sichere Ränder kommen allein aus stil/rahmen.css (data-rahmen), wie in jeder Telefonansicht.
  import { onMount } from "svelte";
  import AnfrageOeffnen from "../AnfrageOeffnen.svelte";
  import AppWeg from "../AppWeg.svelte";
  import { verbindung } from "../../lib/erreichbar.svelte";
  import { auftraege, verfolgen } from "../../lib/auftraege.svelte";
  import { fassung } from "../../lib/fassung.svelte";
  import { gehe, navigation } from "../../lib/navigation.svelte";
  import type { Anfrage, Bereich, EinstellungsReiter } from "../../lib/typen";
  import { verbindungen, verbindungenVerfolgen } from "../../lib/verbindungen.svelte";
  import Einstellungen from "../Einstellungen.svelte";
  import Protokoll from "../Protokoll.svelte";
  import MobilAuftraege from "./MobilAuftraege.svelte";
  import MobilMehr from "./MobilMehr.svelte";

  let { bereiche, oeffnen, einstellungen = [] }: { bereiche: Bereich[]; oeffnen?: (a: Anfrage) => Promise<string> | string;
                                                 einstellungen?: EinstellungsReiter[] } = $props();

  onMount(() => {
    const a = verfolgen();
    const v = verbindungenVerfolgen();
    return () => {
      a();
      v();
    };
  });

  const reiter = $derived(bereiche.some((b) => b.reiter) ? bereiche.filter((b) => b.reiter) : bereiche.slice(0, 2));
  const weitere = $derived(bereiche.filter((b) => !reiter.includes(b)));
  const seite = $derived(navigation.seite || reiter[0]?.schluessel || "auftraege");
  const bereich = $derived(bereiche.find((b) => b.schluessel === seite));
  const unterMehr = $derived(seite === "protokoll" || seite === "einstellungen" || weitere.some((b) => b.schluessel === seite));
  const titel = $derived(bereich?.titel ?? ({ auftraege: "Aufträge", protokoll: "Protokoll", einstellungen: "Einstellungen", mehr: "Mehr" } as Record<string, string>)[seite] ?? "");
  const fehlend = $derived(verbindungen.liste.filter((v) => !v.ok));
  const offen = $derived(auftraege.laufen + auftraege.warten);
</script>

<div class="mobil" data-rahmen="app">
  <div class="t-kopf" data-rahmen="kopf" class:mit-aktionen={!!navigation.aktionen}>
    {#if bereich && navigation.teile.length}
      <button class="rund" aria-label="Zurück" onclick={() => gehe(seite)}><i class="fa-solid fa-chevron-left"></i></button>
    {:else if unterMehr}<button class="rund" aria-label="Zurück" onclick={() => gehe("mehr")}><i class="fa-solid fa-chevron-left"></i></button>{/if}
    <h1>{navigation.titel || titel}</h1>
    {#if navigation.kennzeichen}<span class="pille"><i class="fa-solid {navigation.kennzeichen.symbol}"></i>{navigation.kennzeichen.text}</span>{/if}
    {#if navigation.aktionen}<span class="t-aktionen">{@render navigation.aktionen()}</span>{/if}
    {#if offen && seite !== "auftraege"}<button class="pille aktiv" style="border:0" onclick={() => gehe("auftraege")}><i class="fa-solid fa-gears"></i>{offen}</button>{/if}
  </div>
  {#if !verbindung.ok}
    <AppWeg kompakt />
  {:else if fassung.neu}
    <div class="t-band"><i class="fa-solid fa-rotate" style="margin-top:3px"></i>
      <span style="flex:1">Neue Fassung {fassung.neu}; lädt beim nächsten Wechsel von selbst.</span>
      <button class="rund" aria-label="Jetzt neu laden" onclick={() => location.reload()}><i class="fa-solid fa-rotate"></i></button></div>
  {/if}
  {#if verbindung.ok && fehlend.length}
    <div class="t-band"><i class="fa-solid fa-triangle-exclamation" style="margin-top:3px"></i>
      <span>{#each fehlend as v, i (v.name)}{i ? " " : ""}{v.meldung === "nicht eingerichtet"
        ? `${v.name} nicht eingerichtet; unter Mehr, Einstellungen eintragen.`
        : `${v.name} nicht erreichbar; nichts geht verloren.`}{/each}</span></div>
  {/if}
  <div class="t-inhalt" data-rahmen="inhalt">
    {#if bereich}
      <bereich.seite />
    {:else if seite === "anfrage" && oeffnen}
      <AnfrageOeffnen {oeffnen} />
    {:else if seite === "protokoll"}
      <Protokoll kompakt />
    {:else if seite === "einstellungen"}
      <Einstellungen reiter={einstellungen} />
    {:else if seite === "mehr"}
      <MobilMehr {weitere} />
    {:else}
      <MobilAuftraege />
    {/if}
  </div>
  <nav class="t-reiter" data-rahmen="fuss">
    {#each reiter as b (b.schluessel)}
      <button class:aktiv={seite === b.schluessel} onclick={() => gehe(b.schluessel)}><i class="fa-solid {b.symbol}"></i><span class="t-reiter-name">{b.titel}</span></button>
    {/each}
    <button class:aktiv={seite === "auftraege"} onclick={() => gehe("auftraege")}><i class="fa-solid fa-list-check"></i><span class="t-reiter-name">Aufträge</span></button>
    <button class:aktiv={seite === "mehr" || unterMehr} onclick={() => gehe("mehr")}><i class="fa-solid fa-ellipsis"></i><span class="t-reiter-name">Mehr</span></button>
  </nav>
</div>
