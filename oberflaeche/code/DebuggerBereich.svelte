<script lang="ts">
  // Debugger neben dem Editor (aus der Codeschmiede, WIKI-48; nur am Rechner): Steuerleiste, Zeitleiste aller
  // Schritte, Aufrufstapel, Speicher und Ausgabe bis zum gezeigten Schritt. Der Lauf ist eine fertige Aufzeichnung,
  // darum geht jeder Schritt auch rückwärts. Die gezeigte Zeile meldet der Baustein nach außen (`zeile`), der Editor
  // markiert sie; ebenso die Rahmen dieses Schritts (`rahmen`), deren Werte der Editor beim Überfahren zeigt. Woher
  // der Lauf kommt, weiß nur die Sitzung (DebugSitzung).
  import { untrack } from "svelte";
  import type { Rahmen } from "./aufzeichnung";
  import type { DebugSitzung } from "./debugger/sitzung.svelte";
  import { aufrufstapel, istEintritt, istHalt, springe, start, tiefe, type Ziel } from "./debugger/steuerung";
  import Speicherbild from "./Speicherbild.svelte";

  let { sitzung, sprache, code, zeile = $bindable(null), rahmen = $bindable(null) }: {
    sitzung: DebugSitzung;
    sprache: string;
    /** Code im Editor; weicht er vom aufgezeichneten ab, ist der Lauf veraltet */
    code: string;
    /** gezeigte Zeile, solange der Lauf zum Code passt */
    zeile?: number | null;
    /** Rahmen des gezeigten Schritts mit ihren Variablen, solange der Lauf zum Code passt */
    rahmen?: readonly Rahmen[] | null;
  } = $props();

  let i = $state(0);
  const lauf = $derived(sitzung.lauf);
  const schritte = $derived(lauf?.schritte ?? []);
  const halte = $derived(new Set(sitzung.haltepunkte));
  const veraltet = $derived(sitzung.veraltet(code));
  const aktuell = $derived(schritte[i] ?? null);
  const amEnde = $derived(i === schritte.length - 1);
  const eintritt = $derived(istEintritt(schritte, i));
  const stapel = $derived(aktuell ? aufrufstapel(schritte, i, sitzung.aufruf !== null) : []);
  const ausgabeBisher = $derived(schritte.slice(0, i + 1).map((s) => s.ausgabe).join(""));
  const treffer = $derived(schritte.flatMap((_, k) => (istHalt(schritte, k, halte) ? [k] : [])));
  const maxTiefe = $derived(Math.max(1, ...schritte.map(tiefe)));

  // neuer Lauf: am ersten Haltepunkt beginnen; spätere Änderungen an den Haltepunkten springen nicht
  $effect(() => {
    void sitzung.nummer;
    untrack(() => (i = start(sitzung.lauf?.schritte ?? [], new Set(sitzung.haltepunkte))));
  });
  $effect(() => {
    zeile = aktuell && !veraltet ? aktuell.zeile : null;
    rahmen = aktuell && !veraltet ? aktuell.rahmen : null;
  });

  function gehe(ziel: Ziel) {
    if (schritte.length) i = springe(ziel, schritte, i, halte);
  }

  const KNOEPFE: { ziel: Ziel; symbol: string; titel: string; halt?: boolean; trenner?: boolean }[] = [
    { ziel: "anfang", symbol: "fa-backward-fast", titel: "Zum Anfang" },
    { ziel: "zurueckHalt", symbol: "fa-backward", titel: "Zurück zum vorigen Haltepunkt", halt: true },
    { ziel: "zurueck", symbol: "fa-backward-step", titel: "Einen Schritt zurück", trenner: true },
    { ziel: "hinein", symbol: "fa-arrow-turn-down", titel: "Schritt hinein: die nächste Zeile, auch in eine Funktion" },
    { ziel: "ueber", symbol: "fa-share", titel: "Schritt über: Funktionsaufrufe in einem Zug" },
    { ziel: "hinaus", symbol: "fa-arrow-turn-up", titel: "Schritt hinaus: bis die Funktion zurückkehrt" },
    { ziel: "weiterHalt", symbol: "fa-forward", titel: "Weiter bis zum nächsten Haltepunkt", halt: true },
    { ziel: "ende", symbol: "fa-forward-fast", titel: "Zum Ende" },
  ];

  let leiste: HTMLDivElement | undefined = $state();
  function klickLeiste(e: MouseEvent) {
    if (!leiste || !schritte.length) return;
    const r = leiste.getBoundingClientRect();
    i = Math.min(schritte.length - 1, Math.max(0, Math.floor(((e.clientX - r.left) / r.width) * schritte.length)));
  }
  function tasteLeiste(e: KeyboardEvent) {
    const ziel: Partial<Record<string, Ziel>> = { ArrowLeft: "zurueck", ArrowRight: "hinein", Home: "anfang", End: "ende" };
    const z = ziel[e.key];
    if (!z) return;
    e.preventDefault();
    gehe(z);
  }
  const anteil = (k: number) => `${(k / Math.max(1, schritte.length)) * 100}%`;
  const rahmenName = (name: string) => (name === "Modul" ? "Hauptprogramm" : `${name}()`);
</script>

<div class="debugger" data-sprache={sprache}>
  {#if sitzung.laeuft}
    <p class="debugger-leise"><i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Zeichne den Lauf auf ...</p>
  {:else if sitzung.fehler}
    <div class="debugger-meldung"><i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i><span>{sitzung.fehler}</span></div>
  {/if}

  {#if lauf && !sitzung.laeuft}
    {#if veraltet}
      <div class="debugger-veraltet">
        <i class="fa-solid fa-pen" aria-hidden="true"></i><span>Code geändert: die Aufzeichnung zeigt den alten Stand.</span>
        <button class="debugger-neu" onclick={() => sitzung.neu(code)}><i class="fa-solid fa-rotate-right" aria-hidden="true"></i>Neu</button>
      </div>
    {/if}

    {#if schritte.length}
      <div class="debugger-steuer">
        {#each KNOEPFE as k (k.ziel)}
          <button class="debugger-knopf" class:debugger-halt={k.halt} onclick={() => gehe(k.ziel)} title={k.titel} aria-label={k.titel}><i class="fa-solid {k.symbol}" aria-hidden="true"></i></button>
          {#if k.trenner}<span class="debugger-trenner"></span>{/if}
        {/each}
        <button class="debugger-knopf debugger-stopp" onclick={() => sitzung.beenden()} title="Debugger beenden" aria-label="Debugger beenden"><i class="fa-solid fa-stop" aria-hidden="true"></i></button>
      </div>

      <div class="debugger-stand">
        <span>Schritt <b class="debugger-zahl">{i + 1}</b> von <span class="debugger-zahl">{schritte.length}</span></span>
        {#if aktuell && eintritt}<span>Zeile <b class="debugger-zahl">{aktuell.zeile}</b> ruft {rahmenName(stapel[0].name)} auf</span>
        {:else if aktuell && amEnde && lauf.fehler && lauf.fehlerzeile === aktuell.zeile}<span class="debugger-bricht">Zeile <b class="debugger-zahl">{aktuell.zeile}</b> bricht mit einem Fehler ab</span>
        {:else if aktuell}<span>Zeile <b class="debugger-zahl">{aktuell.zeile}</b> ausgeführt</span>{/if}
        {#if treffer.includes(i)}<span class="debugger-halt-text"><i class="fa-solid fa-circle" aria-hidden="true"></i> Haltepunkt</span>{/if}
      </div>
      {#if halte.size && !treffer.length}<p class="debugger-hinweis">Kein Haltepunkt wurde erreicht, der Debugger steht am Ende.</p>{/if}

      <div class="debugger-zeitleiste" bind:this={leiste} onclick={klickLeiste} onkeydown={tasteLeiste} role="slider" tabindex="0"
           aria-label="Schritt in der Zeitleiste" aria-valuemin={1} aria-valuemax={schritte.length} aria-valuenow={i + 1}
           title="Jeder Strich ist ein Schritt; je höher, desto tiefer im Aufruf">
        <svg viewBox="0 0 {schritte.length} {maxTiefe + 1}" preserveAspectRatio="none" aria-hidden="true">
          {#each schritte as s, k (k)}
            <rect x={k + 0.15} width={0.7} y={maxTiefe - tiefe(s)} height={tiefe(s) + 1} class:debugger-war={k < i} />
          {/each}
        </svg>
        {#each treffer as k (k)}<span class="debugger-treffer" style:left="calc({anteil(k + 0.5)} - 3px)"></span>{/each}
        <span class="debugger-jetzt" style:left={anteil(i)} style:width="max(3px, {anteil(1)})"></span>
      </div>
      <div class="debugger-legende">
        <span><i class="fa-solid fa-circle debugger-halt-farbe" aria-hidden="true"></i>hält am Haltepunkt</span>
        <span><i class="fa-solid fa-square debugger-jetzt-farbe" aria-hidden="true"></i>jetzt</span>
        <span>höher heißt tiefer im Aufruf</span>
      </div>

      <div class="debugger-kopf">Aufrufstapel</div>
      <div class="debugger-stapel">
        {#each stapel as r, n (n)}
          <div><span>{rahmenName(r.name)}</span><span>{n === 0 && eintritt ? "wird aufgerufen" : r.zeile === null ? "" : n === 0 ? `Zeile ${r.zeile}` : `wartet in Zeile ${r.zeile}`}</span></div>
        {/each}
      </div>

      <Speicherbild schritt={aktuell} vorher={i > 0 ? schritte[i - 1] : null} innenZuerst />

      <div class="debugger-kopf">Ausgabe bis hier</div>
      <pre class="debugger-ausgabe">{#if ausgabeBisher}{ausgabeBisher}{:else}<span class="debugger-leer">Noch keine Ausgabe</span>{/if}</pre>
    {/if}

    {#if lauf.gekuerzt}<p class="debugger-hinweis">Aufzeichnung nach {schritte.length} Schritten gekürzt; der Code lief trotzdem zu Ende.</p>{/if}
    {#if lauf.zeitueberschreitung}<p class="debugger-hinweis">Zeit überschritten: der Lauf wurde abgebrochen.</p>{/if}
    {#if lauf.fehler && (amEnde || !schritte.length)}
      <div class="debugger-meldung"><i class="fa-solid fa-bug" aria-hidden="true"></i><span>{lauf.fehler}{lauf.fehlerzeile ? ` (Zeile ${lauf.fehlerzeile})` : ""}</span></div>
    {:else if amEnde && lauf.rueckgabe && sitzung.aufruf}
      <div class="debugger-rueckgabe"><i class="fa-solid fa-flag-checkered" aria-hidden="true"></i><span>{sitzung.aufruf} gibt <b>{lauf.rueckgabe.darstellung}</b> zurück</span></div>
    {/if}
  {/if}
</div>

<style>
  .debugger { display: flex; flex-direction: column; gap: var(--a3); font-family: var(--schrift); color: var(--text); }
  .debugger > * { flex-shrink: 0; }
  .debugger-leise { margin: 0; color: var(--text-2); font-size: var(--klein); }
  .debugger-hinweis { margin: 0; color: var(--text-2); font-size: var(--marke); }
  .debugger-zahl { font-family: var(--schrift-zahl); font-variant-numeric: tabular-nums; }
  .debugger-kopf { margin-bottom: calc(-1 * var(--a2)); font-size: var(--marke); text-transform: uppercase; letter-spacing: .06em; color: var(--text-2); }

  .debugger-steuer { display: flex; flex-wrap: wrap; gap: 3px; align-items: center; }
  .debugger-knopf { width: 30px; height: 30px; padding: 0; display: inline-grid; place-items: center; border: 1px solid var(--rand); border-radius: var(--r2); background: transparent; color: var(--text-2); cursor: pointer; flex: none; }
  .debugger-knopf:hover { color: var(--akzent); border-color: var(--akzent); }
  .debugger-knopf.debugger-halt i, .debugger-halt-text, .debugger-halt-farbe { color: var(--ed-haltepunkt); }
  .debugger-trenner { width: 1px; height: 22px; background: var(--rand); margin: 0 3px; }
  .debugger-stopp { margin-left: auto; }
  .debugger-stopp:hover { color: var(--gefahr); border-color: var(--gefahr); }

  .debugger-stand { display: flex; flex-wrap: wrap; gap: var(--a2) var(--a3); align-items: baseline; font-size: var(--klein); color: var(--text-2); }
  .debugger-stand b { color: var(--text); }
  .debugger-stand .debugger-bricht, .debugger-stand .debugger-bricht b { color: var(--warn); }

  .debugger-zeitleiste { position: relative; height: 46px; padding-top: 10px; border-bottom: 1px solid var(--rand); cursor: pointer; }
  .debugger-zeitleiste:focus-visible { outline: 1px solid var(--akzent); outline-offset: 2px; }
  .debugger-zeitleiste svg { display: block; width: 100%; height: 100%; }
  .debugger-zeitleiste rect { fill: color-mix(in srgb, var(--akzent) 35%, transparent); }
  .debugger-zeitleiste rect.debugger-war { fill: color-mix(in srgb, var(--akzent) 70%, transparent); }
  .debugger-zeitleiste .debugger-jetzt { position: absolute; top: 10px; bottom: 0; background: var(--ed-geaendert); pointer-events: none; }
  .debugger-zeitleiste .debugger-treffer { position: absolute; top: 0; width: 6px; height: 6px; border-radius: 50%; background: var(--ed-haltepunkt); pointer-events: none; }
  .debugger-legende { display: flex; flex-wrap: wrap; gap: var(--a3); margin-top: calc(-1 * var(--a2)); font-size: var(--marke); color: var(--text-3); }
  .debugger-legende i { margin-right: var(--a1); }
  .debugger-jetzt-farbe { color: var(--ed-geaendert); }

  .debugger-stapel { display: flex; flex-direction: column; border: 1px solid var(--rand); }
  .debugger-stapel div { display: flex; justify-content: space-between; gap: var(--a2); padding: var(--a1) var(--a2); font-family: var(--schrift-code); font-size: var(--klein); border-top: 1px solid var(--rand); }
  .debugger-stapel div:first-child { border-top: 0; background: color-mix(in srgb, var(--akzent) 10%, transparent); color: var(--text); }
  .debugger-stapel div span:last-child { color: var(--text-3); font-family: var(--schrift); font-size: var(--marke); white-space: nowrap; }

  .debugger-ausgabe { margin: 0; padding: var(--a2) var(--a3); max-height: 200px; overflow-y: auto; background: var(--ed-konsole); border: 1px solid var(--rand); font-family: var(--schrift-code); font-size: var(--klein); line-height: 1.55; color: var(--ed-konsole-text); white-space: pre-wrap; min-height: 34px; }
  .debugger-ausgabe .debugger-leer { color: var(--text-3); font-style: italic; font-family: var(--schrift); }

  .debugger-meldung { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: var(--a2); padding: var(--a2) var(--a3); border: 1px solid var(--warn); font-size: var(--gross); overflow-wrap: anywhere; }
  .debugger-meldung i { margin-top: var(--a1); color: var(--warn); }
  .debugger-veraltet { display: flex; align-items: center; gap: var(--a2); padding: var(--a2); border: 1px solid var(--warn); color: var(--warn); font-size: var(--klein); }
  .debugger-veraltet .debugger-neu { margin-left: auto; height: 26px; display: inline-flex; align-items: center; gap: var(--a2); padding: 0 var(--a3); border: 1px solid var(--warn); border-radius: var(--r2); background: transparent; color: inherit; font: inherit; cursor: pointer; }
  .debugger-rueckgabe { display: flex; align-items: center; gap: var(--a2); padding: var(--a2); border: 1px solid var(--akzent); background: color-mix(in srgb, var(--akzent) 8%, transparent); font-family: var(--schrift-code); font-size: var(--klein); overflow-wrap: anywhere; }
  .debugger-rueckgabe i { color: var(--akzent); }
</style>
