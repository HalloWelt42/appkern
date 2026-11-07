<script lang="ts">
  // Knopf "Wichtig" an einem Auftrag (Leitstelle docs/ARBEITSLOGIK.md Abschnitt 4, LS-23): der Nutzer markiert ihn
  // ausdrücklich, dann geht er bei der Leitstelle allem vor. Mit der Einstellung "Wichtig bestätigen" (je App, ab Werk an)
  // fragt der Knopf vorher die Leitstelle, wie lange er etwa wartet und wer gerade Vorrang hat, und zeigt das als
  // Rückfrage im Ablauf (nie ein Fenster). `onwichtig` schickt den Auftrag; das Backend legt ihn in `als_wichtig()`.
  import { hole, json } from "../lib/api.svelte";

  type Wichtiger = { anwendung: string; faehigkeit: string; rechner: string | null; zustand: string; seit_s: number };
  type Sicht = {
    einschaetzung: { sofort: boolean; wartezeit_s: number | null; rechner: string | null; grund: string; vor_dir: number;
                     wichtige: Wichtiger[]; abgelehnt: string | null };
    satz: string;
    bestaetigen: boolean;
  };

  let {
    modell,
    faehigkeit = undefined,
    alternativen = [],
    titel = "Wichtig",
    onwichtig,
  }: {
    modell: string;
    faehigkeit?: string;
    alternativen?: string[];
    titel?: string;
    onwichtig: () => void | Promise<void>;
  } = $props();

  let frage = $state<Sicht | null>(null);
  let beschaeftigt = $state(false);
  let fehler = $state("");

  async function klick(): Promise<void> {
    fehler = "";
    beschaeftigt = true;
    try {
      const sicht = await hole<Sicht>("/leitstelle/einschaetzung", { method: "POST", ...json({ modell, faehigkeit, alternativen, wichtig: true }) });
      if (sicht.bestaetigen || sicht.einschaetzung.abgelehnt) frage = sicht;
      else await onwichtig();
    } catch (f) {
      fehler = f instanceof Error ? f.message : String(f);
    } finally {
      beschaeftigt = false;
    }
  }

  async function ja(): Promise<void> {
    beschaeftigt = true;
    try {
      await onwichtig();
      frage = null;
    } finally {
      beschaeftigt = false;
    }
  }

  const andere = $derived(frage?.einschaetzung.wichtige ?? []);
</script>

{#if frage}
  <div class="rueckfrage" role="alertdialog" aria-label="Als wichtig rechnen?">
    <span class="frage">{frage.einschaetzung.abgelehnt ? "Geht so nicht" : "Als wichtig rechnen?"}</span>
    <span>{frage.satz}</span>
    {#if andere.length}
      <span>Schon wichtig: {andere.map((w) => `${w.anwendung}${w.rechner ? ` auf ${w.rechner}` : ""}`).join(", ")}; wer zuerst kam, ist zuerst dran.</span>
    {/if}
    <span class="aktionen">
      <button class="knopf still" onclick={() => (frage = null)} disabled={beschaeftigt}>Abbrechen</button>
      {#if !frage.einschaetzung.abgelehnt}
        <button class="knopf" onclick={ja} disabled={beschaeftigt}>
          <i class="fa-solid {beschaeftigt ? 'fa-circle-notch fa-spin' : 'fa-star'}"></i> Ja, wichtig</button>
      {/if}
    </span>
  </div>
{:else}
  <button class="knopf still" onclick={klick} disabled={beschaeftigt}
          title="Geht bei der Leitstelle allem vor, auch der Sprachausgabe; Laufendes rechnet zu Ende. Nur für diesen Auftrag.">
    <i class="fa-solid {beschaeftigt ? 'fa-circle-notch fa-spin' : 'fa-star'}"></i> {titel}</button>
  {#if fehler}<span class="leise klein">{fehler}</span>{/if}
{/if}
