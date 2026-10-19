<script lang="ts">
  // Die App selbst antwortet nicht: ein Zustand an einer Stelle, mit "Erneut versuchen". Unter dem Kopf als Band
  // (`kompakt` am Telefon), beim Start (`ganz`) als ganze Seite. Die Probe fragt von selbst mit wachsender Pause nach;
  // sobald die App antwortet, holen Kopf und Seiten nach, was fehlt.
  import { pruefen, verbindung } from "../lib/erreichbar.svelte";

  // `nochmal`: was "Erneut versuchen" tut (beim Start: den Start wiederholen); sonst die Probe.
  let { ganz = false, kompakt = false, nochmal }: { ganz?: boolean; kompakt?: boolean; nochmal?: () => Promise<unknown> } = $props();
  let selbst = $state(false);
  const prueft = $derived(selbst || verbindung.prueft);
  const meldung = $derived(verbindung.ok ? "Die App antwortet gerade nicht" : verbindung.meldung);

  async function versuchen() {
    selbst = true;
    try {
      await (nochmal ?? pruefen)();
    } finally {
      selbst = false;
    }
  }
</script>

{#if ganz}
  <div class="anmeldung" style="height:100vh; height:100dvh">
    <div class="anmelde-karte leer-gross" style="width:min(460px, 94vw)">
      <i class="fa-solid fa-plug-circle-xmark"></i>
      <h2>{meldung}</h2>
      <p>Sie läuft vielleicht gerade neu an. Diese Seite versucht es von selbst wieder und macht weiter, sobald die App
        antwortet.</p>
      <button class="knopf primaer" onclick={versuchen} disabled={prueft}>
        <i class="fa-solid fa-rotate"></i> {prueft ? "Prüft ..." : "Erneut versuchen"}</button>
    </div>
  </div>
{:else if kompakt}
  <div class="t-band"><i class="fa-solid fa-plug-circle-xmark" style="margin-top:3px"></i>
    <span style="flex:1">{meldung}. Nichts geht verloren; weiter, sobald sie wieder antwortet.</span>
    <button class="rund" aria-label="Erneut versuchen" onclick={versuchen} disabled={prueft}>
      <i class="fa-solid fa-rotate" class:fa-spin={prueft}></i></button></div>
{:else}
  <div class="band" role="status">
    <i class="fa-solid fa-plug-circle-xmark"></i>
    <span><b>{meldung}.</b> Nichts geht verloren; es geht von selbst weiter, sobald sie wieder antwortet.</span>
    <button class="knopf" onclick={versuchen} disabled={prueft}>{prueft ? "Prüft ..." : "Erneut versuchen"}</button>
  </div>
{/if}
