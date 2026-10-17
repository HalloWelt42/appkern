<script lang="ts" generics="T extends string | number | null">
  // Auswahl als Knopf mit aufklappender Liste (statt nativer Auswahlfelder): zeigt immer die Beschriftung, nie den
  // Wert. Schließt bei Klick daneben und mit Escape.
  let {
    wert = $bindable(),
    optionen,
    symbol = "",
    titel = "",
    klein = false,
    onwahl,
  }: {
    wert: T;
    optionen: { wert: T; titel: string; hinweis?: string }[];
    symbol?: string;
    titel?: string;
    klein?: boolean;
    onwahl?: (w: T) => void;
  } = $props();

  let offen = $state(false);
  let wurzel: HTMLElement;
  const anzeige = $derived(optionen.find((o) => o.wert === wert)?.titel ?? "");

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
    {#if symbol}<i class="fa-solid {symbol}"></i>{/if}{#if anzeige}<span class="auswahl-text">{anzeige}</span>{/if}<i class="fa-solid fa-chevron-down auswahl-pfeil"></i>
  </button>
  {#if offen}
    <span class="auswahl-liste" role="listbox">
      {#each optionen as o (o.wert)}
        <button type="button" role="option" aria-selected={o.wert === wert} class:aktiv={o.wert === wert} onclick={() => waehlen(o.wert)}>
          {o.titel}{#if o.hinweis}<span class="auswahl-hinweis">{o.hinweis}</span>{/if}</button>
      {/each}
    </span>
  {/if}
</span>
