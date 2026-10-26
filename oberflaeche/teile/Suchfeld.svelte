<script lang="ts">
  // Suchfeld (Baustein .suche des Leitstands) mit dem X am Ende: es erscheint, sobald etwas eingegeben ist, leert die
  // Eingabe und lässt den Fokus im Feld. Geleert wird wie getippt (ein Ereignis input), darum merken es gebundene Werte
  // und eigene oninput-Behandlungen gleichermaßen. Alle weiteren Eigenschaften gehen an das Eingabefeld.
  import type { HTMLInputAttributes } from "svelte/elements";

  let { wert = $bindable(""), symbol = "fa-magnifying-glass", klasse = "", feld = $bindable(null), ...eingabe }: {
    wert?: string; symbol?: string; klasse?: string; feld?: HTMLInputElement | null;
  } & Omit<HTMLInputAttributes, "value"> = $props();

  function leeren(): void {
    if (!feld) return;
    feld.value = "";
    wert = "";
    feld.dispatchEvent(new Event("input", { bubbles: true }));
    feld.focus();
  }
</script>

<label class="suche {klasse}">
  <i class="fa-solid {symbol}"></i>
  <input bind:this={feld} bind:value={wert} {...eingabe} />
  {#if wert}
    <button type="button" class="leeren" title="Eingabe leeren" aria-label="Eingabe leeren" onclick={leeren}><i class="fa-solid fa-xmark"></i></button>
  {/if}
</label>
