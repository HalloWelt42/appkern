<script lang="ts">
  // Band unter dem Kopf, solange eine Verbindung fehlt; sagt, was das bedeutet.
  import type { Verbindung } from "../lib/typen";
  import { gehe } from "../lib/navigation.svelte";
  import { pruefen, verbindungen as stand } from "../lib/verbindungen.svelte";

  let { verbindungen }: { verbindungen: Verbindung[] } = $props();

  const FOLGE: Record<string, string> = {
    Leitstelle: "Wartende Aufträge beginnen, sobald sie wieder antwortet; nichts geht verloren.",
    Kellerwolke: "Dateien lassen sich gerade nicht lesen oder speichern; nichts geht verloren.",
  };
  const eingerichtet = $derived(verbindungen.every((v) => v.meldung !== "nicht eingerichtet"));
</script>

<div class="band">
  <i class="fa-solid fa-triangle-exclamation"></i>
  <span>
    {#each verbindungen as v, i (v.name)}
      {#if i}<br />{/if}
      {#if v.meldung === "nicht eingerichtet"}
        <b>{v.name} nicht eingerichtet.</b> Unter Einstellungen, Verbindungen eintragen.
      {:else}
        <b>{v.name} nicht erreichbar.</b> {FOLGE[v.name] ?? v.meldung}
      {/if}
    {/each}
  </span>
  {#if eingerichtet}
    <button class="knopf" onclick={() => pruefen()} disabled={stand.prueft}>{stand.prueft ? "Prüft ..." : "Erneut prüfen"}</button>
  {:else}
    <button class="knopf" onclick={() => gehe("einstellungen")}>Zu den Einstellungen</button>
  {/if}
</div>
