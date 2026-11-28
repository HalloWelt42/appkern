<script lang="ts">
  // Kopf der Schale in der Form "kopf" (KINO-2, nach dem Vorbild der Radio-App, mockups/radio-filter/rechner.html):
  // links der Schriftzug der App in Prägung (Silber oder Gold wie BASIC und PRO der Radio-App) mit Unterzeile, mittig die
  // Pillen-Navigation, die in den Inhalt ragt (Bereiche der App, dann die Aufträge der App), jede Taste mit Tastenlicht;
  // rechts Verbindungen, was die App dort zeigt (`rechts`), Darstellung (Thema und Schrift), Protokoll, Einstellungen und
  // Abmelden. Unter 700 Pixeln stehen in der Navigation nur Symbole, die gewählte mit Namen.
  import type { Snippet } from "svelte";
  import { anzeige, anzeigeSetzen, schriftSchritt, SCHRIFTSTUFEN, THEMEN, type Thema } from "../lib/anzeige.svelte";
  import { auftraege } from "../lib/auftraege.svelte";
  import { pruefen, verbindung } from "../lib/erreichbar.svelte";
  import { gehe } from "../lib/navigation.svelte";
  import { abmelden, ohneAnmeldung, sitzung } from "../lib/sitzung.svelte";
  import type { Bereich, Tastenlicht } from "../lib/typen";
  import { gestoert as istGestoert, verbindungen } from "../lib/verbindungen.svelte";
  import { fest } from "../lib/stelle.svelte";

  let { bereiche, seite, schriftzug, unterzeile = "", praegung = "silber", auftraegeTitel = "Aufträge", rechts }: {
    bereiche: Bereich[]; seite: string; schriftzug?: string; unterzeile?: string; praegung?: "silber" | "gold";
    auftraegeTitel?: string; rechts?: Snippet } = $props();

  const app = $derived(sitzung.app!);
  const konto = $derived(sitzung.konto!);
  const offen = $derived(auftraege.laufen + auftraege.warten);
  const gestoert = $derived(verbindungen.liste.filter(istGestoert));
  let tafel = $state(false);

  const SYMBOL: Record<Thema, string> = { hell: "fa-sun", dunkel: "fa-moon", system: "fa-circle-half-stroke" };
  const schriftIndex = $derived(SCHRIFTSTUFEN.findIndex(([s]) => s === anzeige.schrift));
  const schriftName = $derived(SCHRIFTSTUFEN[schriftIndex]?.[1] ?? "");

  function lichtVon(b: Bereich): Tastenlicht | null {
    return b.licht?.() ?? (seite === b.schluessel ? { farbe: "gruen" } : null);
  }
  const auftragsLicht = $derived<Tastenlicht | null>(auftraege.laufen ? { farbe: "gelb" } : seite === "auftraege" ? { farbe: "gruen" } : null);

  function schliessen(e: MouseEvent) {
    if (tafel && !(e.target as Element).closest(".ak-kopf-darstellung")) tafel = false;
  }
</script>

<svelte:window onclick={schliessen} />

<header class="ak-kopfleiste" use:fest={"oben"}>
  <div class="ak-kopf-marke">
    <a class="ak-schriftzug" data-praegung={praegung} href="/" aria-label={app.name}
       onclick={(e) => { e.preventDefault(); gehe(bereiche[0]?.schluessel ?? "auftraege"); }}>{schriftzug ?? app.name.toUpperCase()}</a>
    {#if unterzeile}<span class="ak-kopf-unterzeile">{unterzeile}</span>{/if}
  </div>

  <nav class="ak-pillen" aria-label="Bereiche"><div class="ak-pillen-schiene">
    {#each bereiche as b, i (b.schluessel)}
      {@const l = lichtVon(b)}
      <button class="ak-pille" type="button" aria-current={seite === b.schluessel ? "page" : undefined}
              title={b.hinweis ? `${b.titel}: ${b.hinweis}` : b.titel} onclick={() => gehe(b.schluessel)}>
        <span class="ak-tastenlicht" data-farbe={l?.farbe ?? ""} class:an={!!l} class:blinkt={l?.blinkt} aria-hidden="true"></span>
        <i class="fa-solid {b.symbol}"></i><span class="ak-pille-text">{b.titel}</span>
        <span class="ak-unsichtbar">(Taste {i + 1})</span>
      </button>
    {/each}
    <button class="ak-pille" type="button" aria-current={seite === "auftraege" ? "page" : undefined}
            title="{auftraegeTitel}: was die App im Hintergrund erledigt{offen ? `, ${offen} offen` : ''}" onclick={() => gehe("auftraege")}>
      <span class="ak-tastenlicht" data-farbe={auftragsLicht?.farbe ?? ""} class:an={!!auftragsLicht} aria-hidden="true"></span>
      <i class="fa-solid fa-gears"></i><span class="ak-pille-text">{auftraegeTitel}</span>
    </button>
  </div></nav>

  <div class="ak-kopf-rechts">
    <!-- Störungen als Taste wie alle anderen: das Tastenlicht trägt den Zustand, ein Druck tut das Naheliegende -->
    {#if !verbindung.ok}
      <button class="knopf ak-kopf-meldung" type="button" title="{verbindung.meldung}: erneut versuchen" onclick={() => pruefen()}>
        <span class="ak-tastenlicht an blinkt" data-farbe="rot" aria-hidden="true"></span>
        <i class="fa-solid fa-plug-circle-xmark"></i><span class="ak-kopf-knopftext">{verbindung.meldung}</span></button>
    {:else if gestoert.length}
      <button class="knopf ak-kopf-meldung" type="button" title={gestoert.map((v) => `${v.name}: ${v.meldung}`).join("\n")}
        onclick={() => gehe("einstellungen")}>
        <span class="ak-tastenlicht an" data-farbe="gelb" aria-hidden="true"></span>
        <i class="fa-solid fa-triangle-exclamation"></i><span class="ak-kopf-knopftext">{gestoert.length === 1 ? `${gestoert[0].name} gestört` : `${gestoert.length} gestört`}</span></button>
    {/if}
    {@render rechts?.()}
    <div class="ak-kopf-darstellung">
      <button class="knopf" type="button" aria-expanded={tafel} title="Darstellung: Thema und Schrift" onclick={() => (tafel = !tafel)}>
        <i class="fa-solid fa-circle-half-stroke"></i><span class="ak-kopf-knopftext">Darstellung</span></button>
      {#if tafel}
        <div class="ak-kopf-tafel" role="dialog" aria-label="Darstellung">
          <h3>Thema</h3>
          <div class="segment" role="group" aria-label="Thema">
            {#each THEMEN as [t, name] (t)}
              <button type="button" class:aktiv={anzeige.thema === t} aria-pressed={anzeige.thema === t} onclick={() => anzeigeSetzen({ thema: t })}>
                <i class="fa-solid {SYMBOL[t]}"></i>{t === "system" ? "System" : name}</button>
            {/each}
          </div>
          {#if anzeige.schrift}
            <h3>Schrift</h3>
            <div class="ak-kopf-schrift">
              <button class="knopf" type="button" aria-label="Schrift kleiner" title="Schrift kleiner" disabled={schriftIndex <= 0} onclick={() => schriftSchritt(-1)}><i class="fa-solid fa-minus"></i></button>
              <output>{schriftName}</output>
              <button class="knopf" type="button" aria-label="Schrift größer" title="Schrift größer" disabled={schriftIndex >= SCHRIFTSTUFEN.length - 1} onclick={() => schriftSchritt(1)}><i class="fa-solid fa-plus"></i></button>
            </div>
          {/if}
        </div>
      {/if}
    </div>
    <button class="rund" type="button" class:aktiv={seite === "protokoll"} title="Protokoll: was in der App geschah" aria-label="Protokoll" onclick={() => gehe("protokoll")}>
      <i class="fa-solid fa-clock-rotate-left"></i></button>
    <button class="rund" type="button" class:aktiv={seite === "einstellungen"} title="Einstellungen: Verbindungen, Zugang, Sicherung, Verhalten" aria-label="Einstellungen" onclick={() => gehe("einstellungen")}>
      <i class="fa-solid fa-sliders"></i></button>
    {#if !ohneAnmeldung()}
      <button class="rund" type="button" title="{konto.name}: {konto.geraet ? 'Gerät trennen' : 'Abmelden'}" aria-label={konto.geraet ? "Gerät trennen" : "Abmelden"} onclick={abmelden}>
        <i class="fa-solid {konto.geraet ? 'fa-link-slash' : 'fa-right-from-bracket'}"></i></button>
    {/if}
  </div>
</header>
