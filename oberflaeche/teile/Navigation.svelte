<script lang="ts">
  // Navigation: Bereiche der App, dann Aufträge, Protokoll, Einstellungen; darunter was die App dort zeigt (`zusatz`,
  // etwa ihre Chats), unten Ansicht (Thema, Schrift), Konto und Fassung. Einklappbar auf Symbole (gemerkt je Browser).
  import type { Snippet } from "svelte";
  import { anzeige, anzeigeSetzen, SCHRIFTEN } from "../lib/anzeige.svelte";
  import { auftraege } from "../lib/auftraege.svelte";
  import { gehe } from "../lib/navigation.svelte";
  import { abmelden, sitzung } from "../lib/sitzung.svelte";
  import type { Bereich } from "../lib/typen";

  let { bereiche, seite, zusatz }: { bereiche: Bereich[]; seite: string; zusatz?: Snippet } = $props();
  const app = $derived(sitzung.app!);
  const konto = $derived(sitzung.konto!);
  const offen = $derived(auftraege.laufen + auftraege.warten);
  const dunkel = $derived(anzeige.thema === "dunkel" || (anzeige.thema === "system" && matchMedia("(prefers-color-scheme: dark)").matches));
</script>

<nav class="nav">
  <div class="nav-oben">
    <div class="nav-gruppe">{bereiche.length ? app.name : "App"}</div>
    <button class="rund" title={anzeige.eingeklappt ? "Seitenleiste ausklappen" : "Seitenleiste einklappen: mehr Platz für den Inhalt"}
            onclick={() => anzeigeSetzen({ eingeklappt: !anzeige.eingeklappt })}>
      <i class="fa-solid {anzeige.eingeklappt ? 'fa-angles-right' : 'fa-angles-left'}"></i></button>
  </div>
  {#each bereiche as b (b.schluessel)}
    {@const zahl = b.zahl?.() ?? 0}
    <button class="nav-eintrag" class:aktiv={seite === b.schluessel} title={b.titel} onclick={() => gehe(b.schluessel)}>
      <i class="fa-solid {b.symbol}"></i><span class="nav-text">{b.titel}</span>{#if zahl}<span class="zahl">{zahl}</span>{/if}
    </button>
  {/each}
  {#if bereiche.length}<div class="nav-gruppe">App</div>{/if}
  <button class="nav-eintrag" class:aktiv={seite === "auftraege"} title="Aufträge" onclick={() => gehe("auftraege")}>
    <i class="fa-solid fa-list-check"></i><span class="nav-text">Aufträge</span>{#if offen}<span class="zahl">{offen}</span>{/if}
  </button>
  <button class="nav-eintrag" class:aktiv={seite === "protokoll"} title="Protokoll" onclick={() => gehe("protokoll")}>
    <i class="fa-solid fa-clock-rotate-left"></i><span class="nav-text">Protokoll</span>
  </button>
  <button class="nav-eintrag" class:aktiv={seite === "einstellungen"} title="Einstellungen" onclick={() => gehe("einstellungen")}>
    <i class="fa-solid fa-sliders"></i><span class="nav-text">Einstellungen</span>
  </button>
  {#if zusatz}<div class="nav-zusatz">{@render zusatz()}</div>{/if}
  <div class="nav-fuss">
    <div class="nav-ansicht">
      <div class="nav-gruppe">Ansicht</div>
      <div class="segment">
        <button class:aktiv={dunkel} onclick={() => anzeigeSetzen({ thema: "dunkel" })}>Dunkel</button>
        <button class:aktiv={!dunkel} onclick={() => anzeigeSetzen({ thema: "hell" })}>Hell</button>
      </div>
      <div class="segment" title="Schriftgröße: macht die ganze App größer oder dichter">
        {#each SCHRIFTEN as [s, t] (s)}<button class:aktiv={anzeige.schrift === s} onclick={() => anzeigeSetzen({ schrift: s })}>{t}</button>{/each}
      </div>
    </div>
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
