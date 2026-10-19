<script lang="ts">
  // Aufträge am Telefon: Filter oben, Karten untereinander, ohne Leiste.
  import { onDestroy } from "svelte";
  import { seitenSignal } from "../../lib/api.svelte";
  import { auftraege, laden, mehrLaden, type Filter } from "../../lib/auftraege.svelte";
  import { beiRueckkehr } from "../../lib/erreichbar.svelte";
  import AuftragZeile from "../AuftragZeile.svelte";

  // ob die App antwortet, zeigt die Schale; sobald sie wieder antwortet, lädt die Liste neu
  const signal = seitenSignal();
  const neu = () => laden(signal).catch(() => {});
  neu();
  onDestroy(beiRueckkehr(() => void neu()));
  function filtern(f: Filter) {
    auftraege.filter = f;
    neu();
  }
  const FILTER: [Filter, string][] = [["offen", "Offen"], ["fertig", "Fertig"], ["fehler", "Fehler"], ["alle", "Alle"]];
  const zahl = (f: Filter) => (f === "offen" ? auftraege.laufen + auftraege.warten : f === "fehler" ? auftraege.fehler : 0);
</script>

<div class="segment" style="margin-bottom:10px">
  {#each FILTER as [f, t] (f)}<button class:aktiv={auftraege.filter === f} onclick={() => filtern(f)}>{t}{zahl(f) ? ` ${zahl(f)}` : ""}</button>{/each}
</div>
{#each auftraege.liste as a (a.id)}
  <AuftragZeile auftrag={a} />
{:else}
  <div class="leer">Keine Aufträge</div>
{/each}
{#if auftraege.liste.length < auftraege.gesamt}
  <button class="knopf" style="width:100%; justify-content:center" onclick={() => mehrLaden(signal).catch(() => {})}>Weitere laden</button>
{/if}
