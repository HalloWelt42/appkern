<script lang="ts" generics="T extends string | number">
  // Knopfleiste mit genau einer Wahl (Baustein .stufen mit .stufenwahl): statt einer Auswahlliste mit wenigen Einträgen.
  // Jede Wahl hat Namen, Symbol und optional eine Farbe aus den Marken; der Name steht im Hinweis beim Überfahren und
  // für Vorleser. Anzeige "symbol": nur Symbole; "gewaehlt": die gewählte trägt ihren Namen; "text": alle mit Namen.
  // Tastatur wie in einer Werkzeugleiste: Tab springt auf die gewählte, die Pfeile (sowie Pos1 und Ende) wandern, Leertaste
  // oder Enter wählt. Wandern wählt nicht, weil eine Wahl oft etwas tut (eine Karte verschieben). Der Wert kommt von
  // außen; onwahl meldet nur eine andere Wahl als die jetzige.
  import type { Wahlstufe } from "../lib/typen";

  let { wert, optionen, beschriftung, anzeige = "symbol", gesperrt = false, gross = false, onwahl }: {
    wert: T;
    optionen: Wahlstufe<T>[];
    /** wofür die Leiste steht, für Vorleser */
    beschriftung: string;
    anzeige?: "symbol" | "gewaehlt" | "text";
    gesperrt?: boolean;
    /** Berührflächen ab 44 Pixeln, die Leiste in voller Breite (Telefon) */
    gross?: boolean;
    onwahl: (w: T) => void;
  } = $props();

  const knoepfe: HTMLButtonElement[] = [];
  const gewaehlt = $derived(optionen.findIndex((o) => o.wert === wert));
  const TASTEN: Record<string, (i: number, n: number) => number> = {
    ArrowRight: (i) => i + 1, ArrowDown: (i) => i + 1, ArrowLeft: (i, n) => i - 1 + n, ArrowUp: (i, n) => i - 1 + n,
    Home: () => 0, End: (_, n) => n - 1,
  };

  function taste(e: KeyboardEvent, i: number): void {
    const ziel = TASTEN[e.key];
    if (!ziel) return;
    e.preventDefault();
    knoepfe[ziel(i, optionen.length) % optionen.length]?.focus();
  }
</script>

<span class="stufen stufenwahl" class:gross role="radiogroup" aria-label={beschriftung} aria-disabled={gesperrt || undefined}>
  {#each optionen as o, i (o.wert)}
    {@const an = o.wert === wert}
    <button type="button" role="radio" aria-checked={an} class:an disabled={gesperrt} bind:this={knoepfe[i]}
            tabindex={i === Math.max(gewaehlt, 0) ? 0 : -1}
            title={o.hinweis ? `${o.titel}: ${o.hinweis}` : o.titel} aria-label={o.titel}
            style={o.farbe ? `--stufe: var(--${o.farbe})` : undefined}
            onclick={() => { if (!an) onwahl(o.wert); }} onkeydown={(e) => taste(e, i)}>
      {#if o.symbol}<i class="fa-solid {o.symbol}" aria-hidden="true"></i>{/if}
      {#if anzeige === "text" || (anzeige === "gewaehlt" && an) || !o.symbol}<span>{o.titel}</span>{/if}
    </button>
  {/each}
</span>
