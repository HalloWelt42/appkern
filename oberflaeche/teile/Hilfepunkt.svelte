<script lang="ts">
  // Hilfepunkt: der kleine i-Knopf an einem Bedienelement. Er öffnet das Hilfefenster genau beim passenden Abschnitt
  // (Tiefenlink); mit `finden` sucht und markiert er dort gleich einen Begriff. Er löst nichts am Bedienelement aus.
  import { hilfe } from "../lib/hilfe.svelte";

  let { thema, abschnitt = "", finden = "", titel = "Hilfe dazu" }: {
    thema: string; abschnitt?: string; finden?: string; titel?: string;
  } = $props();

  function oeffnen(e: MouseEvent): void {
    e.preventDefault();
    e.stopPropagation();
    if (finden) hilfe.finden(thema, finden);
    else hilfe.zeigen(thema, abschnitt || undefined);
  }
</script>

<button type="button" class="hilfepunkt" title={titel} aria-label={titel} onclick={oeffnen}><i class="fa-solid fa-circle-info"></i></button>
