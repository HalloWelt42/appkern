<script lang="ts" generics="T extends string | number | null">
  // Auswahl als Knopf mit aufklappender Liste (statt nativer Auswahlfelder): zeigt immer die Beschriftung, nie den
  // Wert (ohne Wahl den Platzhalter). Schließt bei Klick daneben und mit Escape.
  let {
    wert = $bindable(),
    optionen,
    symbol = "",
    titel = "",
    klein = false,
    platzhalter = "",
    onwahl,
  }: {
    wert: T;
    optionen: { wert: T; titel: string; hinweis?: string; aufgabe?: string }[];
    symbol?: string;
    titel?: string;
    klein?: boolean;
    platzhalter?: string;
    onwahl?: (w: T) => void;
  } = $props();

  let offen = $state(false);
  let wurzel: HTMLElement;
  const gewaehlt = $derived(optionen.find((o) => o.wert === wert));
  const anzeige = $derived(gewaehlt?.titel ?? "");

  function waehlen(w: T) {
    wert = w;
    offen = false;
    onwahl?.(w);
  }

  function draussen(e: MouseEvent) {
    if (offen && wurzel && !wurzel.contains(e.target as Node)) offen = false;
  }
</script>

<svelte:window onclick={draussen} onkeydown={(e) => e.key === "Escape" && (offen = false)} />

<span class="auswahl" bind:this={wurzel}>
  <button class="auswahl-knopf" class:klein type="button" title={titel || undefined} aria-haspopup="listbox" aria-expanded={offen}
          onclick={() => (offen = !offen)}>
    {#if symbol}<i class="fa-solid {symbol}"></i>{/if}{#if anzeige}<span class="auswahl-text">{anzeige}{#if gewaehlt?.aufgabe}<span class="auswahl-aufgabe"> · {gewaehlt.aufgabe}</span>{/if}</span>{:else if platzhalter}<span class="auswahl-text platzhalter">{platzhalter}</span>{/if}<i class="fa-solid fa-chevron-down auswahl-pfeil"></i>
  </button>
  {#if offen}
    <span class="auswahl-liste" role="listbox">
      {#each optionen as o (o.wert)}
        <button type="button" role="option" aria-selected={o.wert === wert} class:aktiv={o.wert === wert} onclick={() => waehlen(o.wert)}>
          {o.titel}{#if o.aufgabe}<span class="auswahl-aufgabe"> · {o.aufgabe}</span>{/if}{#if o.hinweis}<span class="auswahl-hinweis">{o.hinweis}</span>{/if}</button>
      {/each}
    </span>
  {/if}
</span>
