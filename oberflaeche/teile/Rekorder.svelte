<script lang="ts">
  // Aufnehmen (Entwurf der Transkription 1e und Telefon 2): eine Leiste wie der Spieler (Beenden, Anhalten, Pegel,
  // Zeit, Marker), am Telefon unten; Name, Mikrofon, Live-Mitschrift, Sicherung, Signal und Verwerfen als kleine
  // Symbole an festen Plätzen, ein Klick zeigt ihre Erklärung als Blase über dem Text; der Live-Text bekommt den Platz.
  // Beenden legt die Aufnahme über `ablegen` bei der App ab; was danach geschieht, entscheidet der Nutzer mit dem, was
  // die App als `danach` anbietet (oder er verwirft sie dort).
  import { tick, type Snippet } from "svelte";
  import { abbrechen, aufnahme, beenden, markerSetzen, pause, quelleWechseln, tonFortsetzen, verwerfen,
           type Gespeichert, type NachDerAufnahme } from "../lib/aufnahme.svelte";
  import { geraet } from "../lib/geraet.svelte";
  import { marke } from "../lib/zeit";
  import Auswahl from "./Auswahl.svelte";

  // `ort`: wo die App Aufnahmen ablegt ("Aufnahmen"); `ablegen` gibt die Kennung der abgelegten Aufnahme zurück.
  let { kompakt = false, ort, ablegen, liveHinweis = "Der Text erscheint während der Aufnahme.", onfertig, danach }: {
    kompakt?: boolean; ort: string; ablegen: (fertig: { daten: Blob; info: Gespeichert }) => Promise<string>;
    liveHinweis?: string; onfertig?: (meldung: string) => void; danach: Snippet<[NachDerAufnahme]>;
  } = $props();

  let name = $state(aufnahme.name);
  let fehler = $state("");
  let sendet = $state(false);
  let textfeld = $state<HTMLElement>();
  type Symbol = "name" | "mikro" | "live" | "sicherung" | "signal" | "weg";
  let offen = $state<Symbol | null>(null);
  let pegelBreite = $state(0);
  // so viele Säulen (3 px und 2 px Abstand), wie in die Breite passen; die neuesten rechts
  const pegel = $derived(aufnahme.pegel.slice(-Math.max(10, Math.floor(pegelBreite / 5))));
  const signalArt = $derived(aufnahme.pausiert ? "aus" : aufnahme.signal === "angehalten" ? "fehler" : aufnahme.signal === "still" ? "warn" : "gut");

  const geraete = $derived([{ wert: "", titel: "Standard des Systems" }, ...aufnahme.geraete
    .filter((g) => g.id && g.id !== "default").map((g) => ({ wert: g.id, titel: g.name }))]);

  $effect(() => {
    void aufnahme.mitschrift.length;
    void tick().then(() => textfeld?.scrollTo({ top: textfeld.scrollHeight }));
  });

  function umschalten(art: Symbol) {
    offen = offen === art ? null : art;
  }

  // ein Klick neben die Symbole schließt die Blase
  function daneben(e: MouseEvent) {
    if (offen && !(e.target as HTMLElement).closest(".rek-symbole")) offen = null;
  }

  async function abbrechenJetzt() {
    sendet = true;
    try {
      await abbrechen();
      offen = null;
      onfertig?.("Aufnahme verworfen; nichts wurde gespeichert.");
    } catch (f) {
      fehler = (f as Error).message;
      offen = "sicherung";
    } finally {
      sendet = false;
    }
  }

  async function stopp() {
    sendet = true;
    fehler = "";
    try {
      const fertig = await beenden(name);
      if (!fertig) return;
      const id = await ablegen(fertig);
      await verwerfen(fertig.info.id);
      aufnahme.danach = { id, name: name.trim() || aufnahme.name, dauer_s: fertig.info.dauer_ms / 1000,
                          mitschrift: [...aufnahme.mitschrift] };
    } catch (f) {
      fehler = `${(f as Error).message}. Die Aufnahme bleibt auf diesem Gerät und lässt sich später hochladen.`;
      offen = "sicherung";
    } finally {
      sendet = false;
    }
  }
</script>

{#snippet mitschrift(stuecke: { start: number; text: string }[], stand: string)}
  <div class="mitschrift">
    <div class="mitschrift-kopf"><i class="fa-solid fa-closed-captioning"></i> Live-Mitschrift
      {#if stand}<span class="mitschrift-stand">{stand}</span>{/if}</div>
    <div class="mitschrift-text" bind:this={textfeld}>
      {#each stuecke as s, i (i)}<p><span class="zeit">{marke(s.start)}</span>{s.text}</p>{:else}
        <p class="mitschrift-leer">Der Text erscheint nach den ersten Sätzen.</p>{/each}
    </div>
  </div>
{/snippet}

{#snippet symbole()}
  <span class="rek-symbole">
    <button class="rek-symbol" class:offen={offen === "name"} title="Name" aria-label="Name" onclick={() => umschalten("name")}><i class="fa-solid fa-pen"></i></button>
    <button class="rek-symbol" class:fehler={!!aufnahme.fehler} class:offen={offen === "mikro"} title="Mikrofon" aria-label="Mikrofon"
            onclick={() => umschalten("mikro")}><i class="fa-solid fa-microphone"></i></button>
    {#if aufnahme.hoerbar}
      <button class="rek-symbol {aufnahme.live ? 'gut' : 'aus'}" class:offen={offen === "live"} title="Live-Mitschrift" aria-label="Live-Mitschrift"
              onclick={() => umschalten("live")}><i class="fa-solid fa-closed-captioning"></i></button>
    {/if}
    <button class="rek-symbol {fehler ? 'fehler' : 'gut'}" class:offen={offen === "sicherung"} title="Sicherung" aria-label="Sicherung"
            onclick={() => umschalten("sicherung")}><i class="fa-solid fa-floppy-disk"></i></button>
    <button class="rek-symbol {signalArt}" class:offen={offen === "signal"} title="Ton vom Mikrofon" aria-label="Ton vom Mikrofon"
            onclick={() => umschalten("signal")}><i class="fa-solid {signalArt === 'gut' || signalArt === 'aus' ? 'fa-wave-square' : 'fa-triangle-exclamation'}"></i></button>
    <button class="rek-symbol" class:offen={offen === "weg"} title="Verwerfen" aria-label="Verwerfen" onclick={() => umschalten("weg")}
            disabled={sendet}><i class="fa-solid fa-trash-can"></i></button>
    {#if offen}
      <div class="rek-blase" role="dialog" aria-label="Erklärung">
        {#if offen === "name"}
          <b>Name</b>Unter diesem Namen landet die Aufnahme in {ort}.
          <label class="eingabe klein-eingabe" style="margin-top:10px"><input bind:value={name} aria-label="Name der Aufnahme" /></label>
        {:else if offen === "mikro"}
          <b>Mikrofon</b>Wechselt sofort, auch mitten in der Aufnahme.
          {#if aufnahme.fehler}<p class="fehlertext" style="margin:8px 0 0">{aufnahme.fehler}</p>{/if}
          <div class="knopfreihe"><Auswahl wert={aufnahme.geraet} optionen={geraete} onwahl={(g) => quelleWechseln(g)} /></div>
        {:else if offen === "live"}
          <b>Live-Mitschrift</b>{aufnahme.live ? liveHinweis : "Aus: kein Text während der Aufnahme."}
          {#if aufnahme.liveStand}<p style="margin:6px 0 0">{aufnahme.liveStand}</p>{/if}
          <label class="schalter-zeile" style="margin-top:10px"><button class="schalter" class:an={aufnahme.live} aria-label="Live mitschreiben"
                 aria-pressed={aufnahme.live} onclick={() => (aufnahme.live = !aufnahme.live)}></button>Live mitschreiben</label>
        {:else if offen === "sicherung"}
          {#if fehler}<b>Nicht hochgeladen</b>{fehler}{:else}<b>Wird laufend gesichert</b>Jedes Stück liegt sofort auf diesem Gerät und übersteht ein Neuladen.{/if}
        {:else if offen === "signal"}
          {#if signalArt === "fehler"}
            <b>Ton angehalten</b>Der Browser hält den Ton zurück; die Aufnahme bliebe stumm.
            <div class="knopfreihe"><button class="knopf klein primaer" onclick={tonFortsetzen}>Ton freigeben</button></div>
          {:else if signalArt === "warn"}
            <b>Kein Ton seit Sekunden</b>Vom Mikrofon kommt nichts an. Prüfe es oder wähle beim Mikrofon-Symbol ein anderes.
          {:else if signalArt === "aus"}
            <b>Angehalten</b>Weiter geht es mit dem Knopf neben Beenden.
          {:else}
            <b>Ton kommt an</b>Der Pegel zeigt, wie laut; leise Stellen sind normal.
          {/if}
        {:else if offen === "weg"}
          <b>Aufnahme verwerfen?</b>Sie wird nicht gespeichert, auch nicht auf diesem Gerät.
          <div class="knopfreihe"><button class="knopf klein still" onclick={() => (offen = null)}>Behalten</button>
            <button class="knopf klein gefahr" onclick={abbrechenJetzt} disabled={sendet}><i class="fa-solid fa-trash-can"></i> Verwerfen</button></div>
        {/if}
      </div>
    {/if}
  </span>
{/snippet}

{#snippet leiste(mitSymbolen: boolean)}
  <div class="rek-leiste">
    <button class="stopp" title="Beenden und speichern" aria-label="Beenden und speichern" onclick={stopp} disabled={sendet}>
      <i class="fa-solid {sendet ? 'fa-circle-notch fa-spin' : 'fa-stop'}"></i></button>
    <button class="rund pause" title={aufnahme.pausiert ? "Weiter aufnehmen" : "Anhalten"} aria-label={aufnahme.pausiert ? "Weiter aufnehmen" : "Anhalten"}
            onclick={pause} disabled={sendet}><i class="fa-solid {aufnahme.pausiert ? 'fa-play' : 'fa-pause'}"></i></button>
    <span class="rek-pegel" bind:clientWidth={pegelBreite}>{#each pegel as h, i (i)}<span style="height:{Math.max(6, h)}%"></span>{/each}</span>
    <span class="rek-zeit" class:angehalten={aufnahme.pausiert}><span class="punkt"></span>{marke(aufnahme.dauer_ms / 1000)}</span>
    <button class="rund marken" title="Marker setzen" aria-label="Marker setzen" onclick={markerSetzen} disabled={sendet}>
      <i class="fa-solid fa-flag"></i>{#if aufnahme.marker.length}<span class="zahl">{aufnahme.marker.length}</span>{/if}</button>
    {#if mitSymbolen}{@render symbole()}{/if}
  </div>
{/snippet}

<svelte:window onclick={daneben} />

<div class="rekorder" class:kompakt>
  {#if aufnahme.danach}
    {@const d = aufnahme.danach}
    <div class="rekorder-gespeichert">
      <i class="fa-solid fa-circle-check"></i>
      <div><b>{d.name}</b> liegt in {ort} ({marke(d.dauer_s)}). Was soll damit geschehen?</div>
    </div>
    {#if d.mitschrift.length}{@render mitschrift(d.mitschrift, "")}{/if}
    {@render danach(d)}
  {:else}
    <div class="rek">
      {#if !geraet.mobil}{@render leiste(true)}{/if}
      {#if aufnahme.hoerbar}
        <div class="rek-live">
          <div class="kopf-zeile"><i class="fa-solid fa-closed-captioning"></i> Live-Mitschrift
            <span style="margin-left:auto">{aufnahme.live ? aufnahme.liveStand : "aus"}</span></div>
          <div class="text" bind:this={textfeld}>
            {#if aufnahme.live}
              {#each aufnahme.mitschrift as st, i (i)}<p><span class="zeit">{marke(st.start)}</span>{st.text}</p>{:else}
                <p class="mitschrift-leer">Der Text erscheint nach den ersten Sätzen.</p>{/each}
            {:else}
              <p class="mitschrift-leer">Die Live-Mitschrift ist aus; einschalten über das Symbol mit den Untertiteln.</p>
            {/if}
          </div>
        </div>
      {/if}
      {#if geraet.mobil}{@render symbole()}{@render leiste(false)}{/if}
    </div>
  {/if}
</div>
