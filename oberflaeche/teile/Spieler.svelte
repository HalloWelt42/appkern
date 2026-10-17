<script lang="ts">
  // Spieler mit Wellenform (aus dem Transkript, gezeichnet), Sprecherspur, Markern und Tempo. Klick oder Ziehen auf
  // der Wellenform springt; Leertaste spielt und hält an, Pfeile springen 5 s (nicht beim Schreiben in Feldern).
  // `stoppBei`: hält an dieser Zeit an (Bearbeiten, "Nur diesen Beitrag").
  import { arbeit } from "../lib/arbeit.svelte";
  import { marke } from "../lib/zeit";

  interface Spur {
    von: number;
    bis: number;
    farbe: string;
  }

  let {
    src,
    dauer = 0,
    wellenform = null,
    spur = [],
    marker = [],
    zeit = $bindable(0),
    laeuft = $bindable(false),
    stoppBei = null,
    kompakt = false,
  }: {
    src: string;
    dauer?: number;
    wellenform?: number[] | null;
    spur?: Spur[];
    marker?: number[];
    zeit?: number;
    laeuft?: boolean;
    stoppBei?: number | null;
    kompakt?: boolean;
  } = $props();

  const TEMPI = [0.75, 1, 1.25, 1.5, 2];
  let ton: HTMLAudioElement;
  let leinwand: HTMLCanvasElement;
  let breite = $state(0);
  let tempo = $state(1);
  let gesamt = $state(0);
  const laenge = $derived(gesamt || dauer || 1);

  export function springe(t: number, abspielen = false): void {
    if (!ton) return;
    ton.currentTime = Math.max(0, Math.min(t, laenge));
    zeit = ton.currentTime;
    if (abspielen) void ton.play();
  }

  export function umschalten(): void {
    if (!ton) return;
    if (ton.paused) void ton.play();
    else ton.pause();
  }

  export function anhalten(): void {
    ton?.pause();
  }

  function takt() {
    zeit = ton.currentTime;
    if (stoppBei != null && zeit >= stoppBei && !ton.paused) ton.pause();
  }

  function zeichnen() {
    if (!leinwand || !breite) return;
    const dpr = devicePixelRatio || 1;
    const hoehe = leinwand.clientHeight;
    leinwand.width = Math.round(breite * dpr);
    leinwand.height = Math.round(hoehe * dpr);
    const g = leinwand.getContext("2d");
    if (!g) return;
    g.scale(dpr, dpr);
    g.clearRect(0, 0, breite, hoehe);
    const stil = getComputedStyle(leinwand);
    const leise = stil.getPropertyValue("--rand").trim() || "#ccc";
    const laut = stil.getPropertyValue("--akzent").trim() || "#2f7ce0";
    const werte = wellenform?.length ? wellenform : [];
    const saeulen = Math.max(1, Math.floor(breite / 3));
    const gespielt = (zeit / laenge) * breite;
    for (let i = 0; i < saeulen; i++) {
      const w = werte.length ? werte[Math.floor((i / saeulen) * werte.length)] : 30;
      const h = Math.max(2, (w / 100) * (hoehe - 4));
      const x = i * 3;
      g.fillStyle = x < gespielt ? laut : leise;
      g.fillRect(x, (hoehe - h) / 2, 2, h);
    }
  }

  $effect(() => {
    void [zeit, breite, wellenform, laenge];
    zeichnen();
  });

  function zeigen(e: PointerEvent) {
    const r = leinwand.getBoundingClientRect();
    springe(((e.clientX - r.left) / r.width) * laenge);
  }

  function ziehen(e: PointerEvent) {
    if (e.buttons === 1) zeigen(e);
  }

  function tasten(e: KeyboardEvent) {
    const ziel = e.target as HTMLElement;
    if (ziel.closest("input, textarea, [contenteditable]") || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === " ") {
      e.preventDefault();
      umschalten();
    } else if (e.key === "ArrowLeft") springe(zeit - 5);
    else if (e.key === "ArrowRight") springe(zeit + 5);
  }

  function tempoWechseln() {
    tempo = TEMPI[(TEMPI.indexOf(tempo) + 1) % TEMPI.length];
    if (ton) ton.playbackRate = tempo;
  }

  $effect(() => {
    arbeit.wiedergabe = laeuft;
    return () => (arbeit.wiedergabe = false);
  });
</script>

<svelte:window onkeydown={tasten} />

<audio bind:this={ton} {src} preload="metadata" ontimeupdate={takt} onplay={() => (laeuft = true)}
       onpause={() => (laeuft = false)} onended={() => (laeuft = false)}
       onloadedmetadata={() => (gesamt = Number.isFinite(ton.duration) ? ton.duration : 0)}></audio>

<div class={kompakt ? "t-spieler" : "spieler"}>
  <button class="gross" title={laeuft ? "Anhalten (Leertaste)" : "Abspielen (Leertaste)"} onclick={umschalten}>
    <i class="fa-solid {laeuft ? 'fa-pause' : 'fa-play'}"></i></button>
  {#if !kompakt}
    <span class="knopfreihe">
      <button class="rund" title="5 s zurück" onclick={() => springe(zeit - 5)}><i class="fa-solid fa-rotate-left"></i></button>
      <button class="rund" title="5 s vor" onclick={() => springe(zeit + 5)}><i class="fa-solid fa-rotate-right"></i></button>
    </span>
  {/if}
  <div class="welle" bind:clientWidth={breite}>
    <canvas bind:this={leinwand} class="leinwand" onpointerdown={zeigen} onpointermove={ziehen}></canvas>
    <div class="sprecherspur">
      {#each spur as s, i (i)}<span style="position:absolute; left:{(s.von / laenge) * 100}%; width:{Math.max(0.2, ((s.bis - s.von) / laenge) * 100)}%; height:100%; background:{s.farbe}"></span>{/each}
    </div>
    {#each marker as m, i (i)}<i class="fa-solid fa-flag fahne" style="left:{(m / laenge) * 100}%"></i>{/each}
    <div class="abspielkopf" style="left:{(zeit / laenge) * 100}%"></div>
  </div>
  <span class="zeitangabe">{marke(zeit)}{kompakt ? "" : " / "}{#if kompakt}<br />{/if}{marke(laenge)}</span>
  {#if !kompakt}
    <button class="knopf" title="Tempo" onclick={tempoWechseln}><i class="fa-solid fa-gauge"></i> {Math.round(tempo * 100)} %</button>
  {/if}
</div>
