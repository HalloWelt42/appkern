<script lang="ts">
  // Dateien der Kellerwolke als Quelle einer App: blättern wie dort, wählbar ist, was der Zweck erlaubt und noch kein
  // Ergebnis hat. Die App sieht hier nur Namen; erst das Starten stellt je Datei eine Anfrage, mit deren Recht der
  // Auftrag die Datei liest und sein Ergebnis daneben legt. Dateien mit Ergebnis öffnet "Öffnen" über eine Anfrage zum
  // Ansehen und Bearbeiten. Begleiter erscheinen nicht als eigene Zeilen, nur als Stand ihrer Hauptdatei.
  // Was die App einstellen lässt (Sprache, Stimme ...), reicht sie als `optionen` herein; am Telefon gelten die
  // gespeicherten Einstellungen.
  import { onMount, type Snippet } from "svelte";
  import { hole } from "../lib/api.svelte";
  import { beiAuftrag } from "../lib/auftraege.svelte";
  import { wann } from "../lib/format";
  import { geraet } from "../lib/geraet.svelte";
  import { dateiSymbol, daneben, istMedium, waehlen, wahl } from "../lib/kellerwolke";
  import { gehe, navigation } from "../lib/navigation.svelte";
  import type { Auftrag, Seite, WahlEintrag, WahlSeite, WahlZweck } from "../lib/typen";
  import { groesse } from "../lib/zeit";

  // `ordner`: der gezeigte Ordner (null: "Meine Dateien"); `kette` meldet den Weg dorthin an die Seite (Chips, Hoch).
  let { zweck, ordner, suche = "", kette = $bindable([]), optionen }: {
    zweck: WahlZweck; ordner: string | null; suche?: string; kette?: WahlSeite["kette"]; optionen?: Snippet;
  } = $props();

  let seite = $state<WahlSeite | null>(null);
  let laufend = $state<Record<string, Auftrag>>({});   // Datei -> laufender Auftrag des Zwecks
  let gewaehlt = $state<string[]>([]);
  let fehler = $state("");
  let meldung = $state("");
  let startet = $state(false);
  const SEITE = 100;   // Zeilen je Seite; ein Ordner kann groß sein
  let ab = $state(0);

  const waehlbar = (e: WahlEintrag) =>
    e.typ === "datei" && (zweck.waehlbar ?? ((x: WahlEintrag) => istMedium(x.inhaltstyp)))(e, begleiter[e.id] ?? []);

  async function laden() {
    fehler = "";
    try {
      seite = await wahl(ordner);
      kette = seite.kette;
      if (geraet.mobil) navigation.titel = seite.kette.length > 1 ? seite.kette.at(-1)!.name : "Meine Dateien";
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  async function laufendeLaden() {
    const offen = await hole<Seite<Auftrag>>("/auftraege?zustand=wartet&zustand=laeuft&grenze=200");
    laufend = Object.fromEntries(offen.eintraege.filter((a) => a.art === zweck.auftrag).map((a) => [zweck.quelle(a), a]));
  }

  onMount(() => {
    if (geraet.mobil) navigation.kennzeichen = { symbol: "fa-cloud", text: "Kellerwolke" };
    void laden();
    void laufendeLaden().catch(() => {});
    return beiAuftrag((a) => {
      if (a.art !== zweck.auftrag) return;
      const quelle = zweck.quelle(a);
      if (a.zustand === "wartet" || a.zustand === "laeuft") laufend = { ...laufend, [quelle]: a };
      else if (laufend[quelle]) {
        const { [quelle]: _fertig, ...rest } = laufend;
        laufend = rest;
        if (!Object.keys(rest).length) meldung = "";      // "wird bearbeitet" stimmt nicht mehr
        void laden().then(() => {
          if (a.zustand !== "fertig") fehler = a.fehler ?? `${zweck.woerter.tun} gescheitert`;
        });
      }
    });
  });

  // Begleiter je Hauptdatei (aus derselben Liste; sie liegen im selben Ordner)
  const begleiter = $derived.by(() => {
    const je: Record<string, WahlEintrag[]> = {};
    for (const e of seite?.eintraege ?? []) if (e.haupt_id) (je[e.haupt_id] ??= []).push(e);
    return je;
  });
  const sichtbar = $derived((seite?.eintraege ?? []).filter((e) => !e.haupt_id && (!suche.trim() || e.name.toLowerCase().includes(suche.trim().toLowerCase()))));
  const zeilen = $derived(sichtbar.slice(ab, ab + SEITE));
  const ordnerZeilen = $derived(zeilen.filter((e) => e.typ === "ordner"));
  const wahlZeilen = $derived(zeilen.filter(waehlbar));

  let letzteSuche = "";
  $effect(() => {
    if (suche !== letzteSuche) {
      letzteSuche = suche;
      ab = 0;
    }
  });

  type Stand = "offen" | "laeuft" | "fertig";
  function stand(e: WahlEintrag): Stand {
    if (laufend[e.id]) return "laeuft";
    return (begleiter[e.id] ?? []).some((b) => b.rolle !== null && zweck.ergebnis.includes(b.rolle)) ? "fertig" : "offen";
  }

  function standText(e: WahlEintrag): string {
    const s = stand(e);
    if (s === "fertig") return zweck.woerter.fertig;
    if (s === "laeuft") {
      const a = laufend[e.id];
      return a.zustand === "wartet" ? "wartet" : `${a.schritt?.split(",")[0] || "läuft"}${a.fortschritt != null ? ` ${Math.round(a.fortschritt * 100)} %` : ""}`;
    }
    return zweck.woerter.offen;
  }

  function metazeile(e: WahlEintrag): string {
    if (e.typ === "ordner") return ["Ordner", e.kinder_anzahl != null ? `${e.kinder_anzahl} ${e.kinder_anzahl === 1 ? "Eintrag" : "Einträge"}` : ""].filter(Boolean).join(" · ");
    if (!waehlbar(e)) return [zweck.woerter.andere, groesse(e.groesse)].filter(Boolean).join(" · ");
    const format = e.name.includes(".") ? e.name.slice(e.name.lastIndexOf(".") + 1).toUpperCase() : "";
    return [format, groesse(e.groesse), wann(e.geaendert_am), daneben((begleiter[e.id] ?? []).map((b) => b.rolle))].filter(Boolean).join(" · ");
  }

  const hinein = (e: WahlEintrag) => gehe(zweck.ordnerAdresse(e.id));

  function umschalten(e: WahlEintrag) {
    if (stand(e) !== "offen") return;
    gewaehlt = gewaehlt.includes(e.id) ? gewaehlt.filter((x) => x !== e.id) : zweck.einzeln ? [e.id] : [...gewaehlt, e.id];
  }

  async function oeffnen(e: WahlEintrag) {
    fehler = "";
    try {
      const { anfrage } = await waehlen(e.id, "oeffnen");
      gehe(`anfrage/${anfrage.id}`);
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  // Zeile antippen (Telefon): Ordner hinein, fertige öffnen, sonst wählen
  function antippen(e: WahlEintrag) {
    if (e.typ === "ordner") hinein(e);
    else if (stand(e) === "fertig") void oeffnen(e);
    else umschalten(e);
  }

  async function starten() {
    startet = true;
    fehler = "";
    try {
      meldung = await zweck.starten(gewaehlt);
      gewaehlt = [];
      await laufendeLaden();
    } catch (f) {
      fehler = (f as Error).message;
    } finally {
      startet = false;
    }
  }
</script>

{#snippet pille(e: WahlEintrag)}
  {@const s = stand(e)}
  <span class="stand-pille {s}">
    {#if s === "laeuft"}<i class="fa-solid fa-circle-notch fa-spin"></i>{/if} {standText(e)}</span>
{/snippet}

{#snippet seitenzeile()}
  {#if sichtbar.length > SEITE}
    <div class="seitenzeile"><span>{ab + 1} bis {Math.min(ab + SEITE, sichtbar.length)} von {sichtbar.length}</span>
      <button class="knopf" disabled={ab === 0} onclick={() => (ab = Math.max(0, ab - SEITE))}><i class="fa-solid fa-chevron-left"></i> Zurück</button>
      <button class="knopf" disabled={ab + SEITE >= sichtbar.length} onclick={() => (ab += SEITE)}>Weiter <i class="fa-solid fa-chevron-right"></i></button>
    </div>
  {/if}
{/snippet}

{#snippet startknopf()}
  <button class="knopf primaer" onclick={starten} disabled={startet}>
    <i class="fa-solid {startet ? 'fa-circle-notch fa-spin' : 'fa-play'}"></i> {zweck.woerter.tun}</button>
{/snippet}

{#if geraet.mobil}
  <div class="t-ansicht">
    <div class="hinweis-band"><i class="fa-solid fa-shield-halved"></i><span>{zweck.woerter.hinweisKurz}</span></div>
    {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
    {#if meldung}<p class="leer" style="padding:6px 4px">{meldung}</p>{/if}
    {#if ordnerZeilen.length}
      <div class="t-gruppe">Ordner</div>
      <div class="t-liste">
        {#each ordnerZeilen as e (e.id)}
          <button class="t-zeile" onclick={() => hinein(e)}><i class="fa-solid fa-folder"></i>
            <span class="t-text"><span class="t-name">{e.name}</span><span class="t-meta">{metazeile(e).replace(/^Ordner · /, "")}</span></span>
            <i class="fa-solid fa-chevron-right" style="color:var(--text-3)"></i></button>
        {/each}
      </div>
    {/if}
    <div class="t-gruppe">{zweck.woerter.gruppe}</div>
    <div class="t-liste">
      {#each wahlZeilen as e (e.id)}
        {@const s = stand(e)}
        <button class="t-zeile" class:gewaehlt={gewaehlt.includes(e.id)} onclick={() => antippen(e)}>
          {#if gewaehlt.includes(e.id)}<i class="fa-solid fa-circle-check" style="color:var(--akzent)"></i>
          {:else}<i class="fa-solid {dateiSymbol(e.typ, e.inhaltstyp)}"></i>{/if}
          <span class="t-text"><span class="t-name">{e.name}</span>
            <span class="t-meta">{[groesse(e.groesse), s === "fertig" ? `${zweck.woerter.fertig}, antippen öffnet` : standText(e)].filter(Boolean).join(" · ")}</span></span>
          {#if s === "fertig"}<i class="fa-solid fa-chevron-right" style="color:var(--text-3)"></i>
          {:else if s === "laeuft"}<span class="stand-pille laeuft"><i class="fa-solid fa-circle-notch fa-spin"></i></span>{/if}
        </button>
      {:else}
        <div class="leer">{seite ? zweck.woerter.leer : "Lädt ..."}</div>
      {/each}
    </div>
    {@render seitenzeile()}
    {#if gewaehlt.length}
      <div class="t-spieler t-wahlleiste">
        <b>{gewaehlt.length} gewählt</b>
        {@render startknopf()}
      </div>
    {/if}
  </div>
{:else}
  <div class="hinweis-band"><i class="fa-solid fa-shield-halved"></i><span>{zweck.woerter.hinweis}</span></div>
  {#if meldung}<p class="leer" style="padding:6px 4px 14px; text-align:left">{meldung}</p>{/if}
  {#if fehler}<div class="fehlertext" style="margin-bottom:12px">{fehler}</div>{/if}
  {#if gewaehlt.length}
    <div class="optionen">
      <span class="titel"><i class="fa-solid {zweck.woerter.symbol}"></i> {gewaehlt.length} gewählt</span>
      {@render optionen?.()}
      <span class="knopfzeile" style="margin-left:auto">
        <button class="knopf still" onclick={() => (gewaehlt = [])}>Auswahl aufheben</button>
        {@render startknopf()}
      </span>
    </div>
  {/if}
  {#each zeilen as e (e.id)}
    {#if e.typ === "ordner"}
      <div class="zeile ordner-zeile" role="button" tabindex="0" onclick={() => hinein(e)} onkeydown={(k) => k.key === "Enter" && hinein(e)}>
        <span class="art"><i class="fa-solid fa-folder"></i></span>
        <div style="min-width:0"><div class="name">{e.name}</div><div class="meta">{metazeile(e)}</div></div>
        <span></span><i class="fa-solid fa-chevron-right" style="color:var(--text-3); padding-right:10px"></i>
      </div>
    {:else if waehlbar(e)}
      <div class="zeile" class:gewaehlt={gewaehlt.includes(e.id)} role="button" tabindex="0"
           onclick={() => umschalten(e)} onkeydown={(k) => k.key === "Enter" && umschalten(e)}>
        <span class="art"><i class="fa-solid {dateiSymbol(e.typ, e.inhaltstyp)}"></i></span>
        <div style="min-width:0"><div class="name">{e.name}</div><div class="meta">{metazeile(e)}</div></div>
        {@render pille(e)}
        {#if stand(e) === "fertig"}
          <button class="knopf still" title="In der App öffnen" onclick={(k) => { k.stopPropagation(); void oeffnen(e); }}>
            <i class="fa-solid fa-up-right-from-square"></i> Öffnen</button>
        {:else}<span></span>{/if}
      </div>
    {:else}
      <div class="zeile nicht-waehlbar" title={zweck.woerter.nichtWaehlbar}>
        <span class="art"><i class="fa-solid {dateiSymbol(e.typ, e.inhaltstyp)}"></i></span>
        <div style="min-width:0"><div class="name">{e.name}</div><div class="meta">{metazeile(e)}</div></div>
        <span></span><span></span>
      </div>
    {/if}
  {:else}
    {#if seite}<p class="leer">{suche ? "Nichts gefunden." : "Dieser Ordner ist leer."}</p>{:else if !fehler}<p class="leer">Lädt ...</p>{/if}
  {/each}
  {#if wahlZeilen.some((e) => stand(e) === "offen")}
    <p class="leer" style="padding:14px">{zweck.woerter.anleitung}</p>
  {/if}
  {@render seitenzeile()}
{/if}
