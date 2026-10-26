<script lang="ts">
  // Eine Einstellung der App als Zeile des Leitstands (Baustein .einstellung): Name, ein Satz, was sie bewirkt, und das
  // passende Bedienelement: Schalter, Zahl mit Schritten, Auswahl mit lesbaren Namen (auch aus dem Angebot des Systems,
  // mit eigenem Wert, wo erlaubt), Text, Liste, Geheimnis mit Auge, Kopieren und Ändern. Geänderte Werte tragen einen
  // Punkt, bis sie gespeichert sind (Entwurf in lib/einstellungen.svelte.ts). Mit `thema` sitzt ein Hilfepunkt am Namen.
  import { einstellungen, einstellungsAngebot, einstellungsGeheimnis, einstellungSetzen, einstellungsWert } from "../lib/einstellungen.svelte";
  import type { Feld, Option } from "../lib/typen";
  import { kopieren } from "../lib/zwischenablage";
  import Auswahl from "./Auswahl.svelte";
  import Hilfepunkt from "./Hilfepunkt.svelte";

  let { feld, thema = "", abschnitt = "", melden = () => {} }: {
    feld: Feld; thema?: string; abschnitt?: string; melden?: (text: string) => void;
  } = $props();

  const EIGEN = "\u0000eigen";
  const HERKUNFT = { gespeichert: "", umgebung: " (gesetzt über die Umgebung des Rechners)", vorgabe: "" } as const;
  const v = $derived(einstellungsWert(feld.name));
  const geaendert = $derived(feld.name in einstellungen.entwurf);
  let aufgedeckt = $state("");
  let neuGeheim = $state("");
  let geheimAendern = $state(false);
  let eigen = $state(false);
  let angebot = $state<Option[]>([]);
  let eigenerWert = $state(true);
  let stand = $state("");
  $effect(() => {
    if (!feld.angebot) return;
    void einstellungsAngebot(feld.name).then((a) => {
      angebot = a.optionen;
      eigenerWert = a.eigener_wert;
      stand = a.stand;
    }).catch(() => {
      angebot = [];
      eigenerWert = true;
    });
  });

  // Auswahl: aus dem Angebot (der eingetragene Wert steht immer mit drin) oder aus den festen Optionen
  const optionen = $derived.by((): Option[] => {
    if (!feld.angebot) return feld.optionen.map((o) => ({ wert: o, titel: feld.beschriftungen[o] ?? o, hinweis: "" }));
    const liste = [...angebot];
    const jetzt = String(v ?? "");
    if (jetzt && !liste.some((o) => o.wert === jetzt)) liste.unshift({ wert: jetzt, titel: jetzt, hinweis: "eingetragen" });
    if (eigenerWert && feld.art !== "liste") liste.push({ wert: EIGEN, titel: "Eigener Wert ...", hinweis: "" });
    return liste;
  });
  function waehlen(w: string): void {
    if (w === EIGEN) eigen = true;
    else {
      eigen = false;
      einstellungSetzen(feld.name, w);
    }
  }
  function umschalten(w: string): void {
    const liste = Array.isArray(v) ? (v as string[]) : [];
    einstellungSetzen(feld.name, liste.includes(w) ? liste.filter((x) => x !== w) : [...liste, w]);
  }

  const schritt = $derived(feld.schritt ?? 1);
  const stellen = $derived(String(schritt).split(".")[1]?.length ?? 0);
  function zahlSetzen(d: number): void {
    const r = Math.round((Number(v ?? 0) + d) / schritt) * schritt;
    einstellungSetzen(feld.name, Math.max(feld.kleinste ?? -Infinity, Math.min(feld.groesste ?? Infinity, Number(r.toFixed(4)))));
  }

  async function aufdecken(): Promise<void> {
    if (aufgedeckt) return void (aufgedeckt = "");
    try {
      aufgedeckt = await einstellungsGeheimnis(feld.name);
    } catch {
      melden(`${feld.titel} ließ sich nicht aufdecken`);
    }
  }
  async function geheimKopieren(): Promise<void> {
    try {
      melden((await kopieren(aufgedeckt || (await einstellungsGeheimnis(feld.name)))) ? "Kopiert"
        : "Kopieren ging nicht; aufgedeckt lässt sich der Wert markieren");
    } catch {
      melden(`${feld.titel} ließ sich nicht kopieren`);
    }
  }
</script>

<div class="einstellung" class:geaendert>
  <div>
    <div class="name">{feld.titel}{#if thema}<Hilfepunkt {thema} {abschnitt} titel="Hilfe zu {feld.titel}" />{/if}{#if geaendert}<span
      class="einstellung-punkt" title="Geändert, noch nicht gespeichert"></span>{/if}</div>
    <div class="erklaerung">{feld.beschreibung}{HERKUNFT[feld.herkunft]}{#if stand} · {stand}{/if}</div>
  </div>
  <div class="wert">
    {#if feld.art === "schalter"}
      <button class="schalter" class:an={!!v} type="button" role="switch" aria-checked={!!v} aria-label={feld.titel}
              onclick={() => einstellungSetzen(feld.name, !v)}></button>
    {:else if feld.art === "zahl"}
      <span class="einstellung-zahl">
        <button type="button" class="knopf symbol klein" title="{feld.titel} verringern" aria-label="{feld.titel} verringern" onclick={() => zahlSetzen(-schritt)}><i class="fa-solid fa-minus"></i></button>
        <b class="zahl">{Number(v ?? 0).toLocaleString("de-DE", { minimumFractionDigits: stellen, maximumFractionDigits: stellen })}</b>
        <button type="button" class="knopf symbol klein" title="{feld.titel} erhöhen" aria-label="{feld.titel} erhöhen" onclick={() => zahlSetzen(schritt)}><i class="fa-solid fa-plus"></i></button>
        {#if feld.einheit}<span class="einheit">{feld.einheit}</span>{/if}
      </span>
    {:else if feld.art === "liste" && feld.angebot}
      <span class="einstellung-chips">
        {#each optionen as o (o.wert)}
          {@const an = Array.isArray(v) && (v as string[]).includes(o.wert)}
          <button type="button" class="chip" class:aktiv={an} aria-pressed={an} title={o.hinweis} onclick={() => umschalten(o.wert)}>
            <i class="fa-solid {an ? 'fa-square-check' : 'fa-square'}"></i>{o.titel}</button>
        {/each}
      </span>
    {:else if feld.art === "liste"}
      <input class="eingabe einstellung-text" value={(Array.isArray(v) ? v : []).join(", ")} aria-label={feld.titel} placeholder="mehrere mit Komma"
             onchange={(e) => einstellungSetzen(feld.name, e.currentTarget.value.split(",").map((x) => x.trim()).filter(Boolean))} />
    {:else if feld.art === "geheimnis"}
      {#if geheimAendern}
        <span class="einstellung-reihe">
          <input class="eingabe einstellung-text" bind:value={neuGeheim} placeholder="Neuer Wert" aria-label="Neuer Wert für {feld.titel}" autocomplete="off" />
          <button type="button" class="knopf klein ohne" onclick={() => { geheimAendern = false; neuGeheim = ""; }}>Abbrechen</button>
          <button type="button" class="knopf klein" disabled={!neuGeheim.trim()}
                  onclick={() => { einstellungSetzen(feld.name, neuGeheim.trim()); geheimAendern = false; neuGeheim = ""; }}><i class="fa-solid fa-check"></i>Übernehmen</button>
        </span>
      {:else}
        <span class="einstellung-reihe">
          <code class="einstellung-geheim">{geaendert ? "neu, noch nicht gespeichert" : aufgedeckt || (feld.gesetzt ? String(feld.wert ?? "") : "nicht gesetzt")}</code>
          {#if feld.gesetzt && !geaendert}
            <button type="button" class="knopf symbol klein ohne" title={aufgedeckt ? "Wieder verdecken" : "Ganz zeigen"} aria-label={aufgedeckt ? "Verdecken" : "Aufdecken"}
                    onclick={aufdecken}><i class="fa-solid {aufgedeckt ? 'fa-eye-slash' : 'fa-eye'}"></i></button>
            <button type="button" class="knopf symbol klein ohne" title="Ganzen Wert kopieren" aria-label="Kopieren" onclick={geheimKopieren}><i class="fa-solid fa-copy"></i></button>
          {/if}
          <button type="button" class="knopf symbol klein ohne" title="Einen neuen Wert eintragen" aria-label="Ändern" onclick={() => (geheimAendern = true)}><i class="fa-solid fa-pen"></i></button>
        </span>
      {/if}
    {:else if (feld.art === "auswahl" || feld.angebot) && !eigen}
      {#if optionen.length <= 4 && optionen.every((o) => o.titel.length <= 14) && !feld.angebot}
        <span class="stufen">{#each optionen as o (o.wert)}<button type="button" class:an={v === o.wert} onclick={() => waehlen(o.wert)}>{o.titel}</button>{/each}</span>
      {:else}
        <Auswahl wert={String(v ?? "")} titel={feld.titel} {optionen} onwahl={waehlen} />
      {/if}
    {:else}
      <span class="einstellung-reihe">
        <input class="eingabe einstellung-text" value={String(v ?? "")} aria-label={feld.titel}
               onchange={(e) => einstellungSetzen(feld.name, e.currentTarget.value.trim())} />
        {#if eigen}<button type="button" class="knopf klein ohne" title="Zurück zur Auswahl" onclick={() => (eigen = false)}><i class="fa-solid fa-list"></i>Auswahl</button>{/if}
      </span>
    {/if}
  </div>
</div>
