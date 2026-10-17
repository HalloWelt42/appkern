<script lang="ts">
  // Navigation: Bereiche der App, dann Aufträge, Protokoll, Einstellungen; unten Konto und Fassung.
  import { auftraege } from "../lib/auftraege.svelte";
  import { gehe } from "../lib/navigation.svelte";
  import { abmelden, sitzung } from "../lib/sitzung.svelte";
  import type { Bereich } from "../lib/typen";

  let { bereiche, seite }: { bereiche: Bereich[]; seite: string } = $props();
  const app = $derived(sitzung.app!);
  const konto = $derived(sitzung.konto!);
  const offen = $derived(auftraege.laufen + auftraege.warten);
</script>

<nav class="nav">
  {#if bereiche.length}
    <div class="nav-gruppe">{app.name}</div>
    {#each bereiche as b (b.schluessel)}
      <button class="nav-eintrag" class:aktiv={seite === b.schluessel} title={b.titel} onclick={() => gehe(b.schluessel)}>
        <i class="fa-solid {b.symbol}"></i><span class="nav-text">{b.titel}</span>
      </button>
    {/each}
  {/if}
  <div class="nav-gruppe">App</div>
  <button class="nav-eintrag" class:aktiv={seite === "auftraege"} title="Aufträge" onclick={() => gehe("auftraege")}>
    <i class="fa-solid fa-list-check"></i><span class="nav-text">Aufträge</span>{#if offen}<span class="zahl">{offen}</span>{/if}
  </button>
  <button class="nav-eintrag" class:aktiv={seite === "protokoll"} title="Protokoll" onclick={() => gehe("protokoll")}>
    <i class="fa-solid fa-clock-rotate-left"></i><span class="nav-text">Protokoll</span>
  </button>
  <button class="nav-eintrag" class:aktiv={seite === "einstellungen"} title="Einstellungen" onclick={() => gehe("einstellungen")}>
    <i class="fa-solid fa-sliders"></i><span class="nav-text">Einstellungen</span>
  </button>
  <div class="nav-fuss">
    <div class="konto">
      <span class="bild">{konto.name.slice(0, 1).toUpperCase()}</span>
      <span class="konto-text"><div class="wer">{konto.name}</div><div class="wie">{konto.geraet ? "gekoppeltes Gerät" : "angemeldet mit Passwort"}</div></span>
      <button class="rund" title={konto.geraet ? "Gerät trennen (zum Wiederkommen neu koppeln)" : "Abmelden"} onclick={abmelden}>
        <i class="fa-solid {konto.geraet ? 'fa-link-slash' : 'fa-right-from-bracket'}"></i>
      </button>
    </div>
    <div class="fassung">{app.name} {app.fassung} · Appkern {app.appkern}</div>
  </div>
</nav>
