<script lang="ts">
  // Mehr am Telefon: weitere Bereiche, Protokoll, Einstellungen, Verbindungen, Anzeige, Konto.
  import { anzeige, anzeigeSetzen, THEMEN } from "../../lib/anzeige.svelte";
  import { gehe } from "../../lib/navigation.svelte";
  import { abmelden, sitzung } from "../../lib/sitzung.svelte";
  import type { Bereich } from "../../lib/typen";
  import { verbindungen } from "../../lib/verbindungen.svelte";

  let { weitere }: { weitere: Bereich[] } = $props();
  const konto = $derived(sitzung.konto!);
  const app = $derived(sitzung.app!);
</script>

<div class="t-liste">
  {#each weitere as b (b.schluessel)}
    <button class="t-zeile" onclick={() => gehe(b.schluessel)}><i class="fa-solid {b.symbol}"></i><span class="t-text"><span class="t-name">{b.titel}</span></span><i class="fa-solid fa-chevron-right" style="font-size:15px; width:auto"></i></button>
  {/each}
  <button class="t-zeile" onclick={() => gehe("protokoll")}><i class="fa-solid fa-clock-rotate-left"></i><span class="t-text"><span class="t-name">Protokoll</span></span><i class="fa-solid fa-chevron-right" style="font-size:15px; width:auto"></i></button>
  <button class="t-zeile" onclick={() => gehe("einstellungen")}><i class="fa-solid fa-sliders"></i><span class="t-text"><span class="t-name">Einstellungen</span></span><i class="fa-solid fa-chevron-right" style="font-size:15px; width:auto"></i></button>
</div>

<div class="t-gruppe">Verbindungen</div>
<div class="t-liste">
  {#each verbindungen.liste as v (v.name)}
    <div class="t-zeile"><i class="fa-solid fa-circle" style="font-size:12px; color:var({v.ok ? '--gut' : '--warn'})"></i>
      <span class="t-text"><div class="t-name">{v.name}</div><div class="t-meta">{v.meldung}</div></span></div>
  {/each}
</div>

<div class="t-gruppe">Anzeige auf diesem Telefon</div>
<div class="t-liste" style="padding: 10px 14px">
  <div class="t-meta" style="color:var(--text-2)">Thema</div>
  <div class="segment" style="margin-top:6px">{#each THEMEN as [s, t] (s)}<button class:aktiv={anzeige.thema === s} onclick={() => anzeigeSetzen({ thema: s })}>{t}</button>{/each}</div>
</div>

<div class="t-gruppe">Konto</div>
<div class="t-liste">
  <div class="t-zeile"><i class="fa-solid {konto.geraet ? 'fa-mobile-screen' : 'fa-user'}"></i>
    <span class="t-text"><div class="t-name">{konto.name}</div><div class="t-meta">{konto.geraet ? "gekoppeltes Gerät" : "angemeldet mit Passwort"}</div></span></div>
  <button class="t-zeile gefahr" onclick={abmelden}><i class="fa-solid {konto.geraet ? 'fa-link-slash' : 'fa-right-from-bracket'}"></i>
    <span class="t-text"><div class="t-name">{konto.geraet ? "Gerät trennen" : "Abmelden"}</div>{#if konto.geraet}<div class="t-meta">meldet ab; zum Wiederkommen neu koppeln</div>{/if}</span></button>
</div>
<p class="fassung" style="text-align:center; padding:14px">{app.name} {app.fassung} · Appkern {app.appkern}</p>
