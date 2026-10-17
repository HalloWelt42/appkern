<script lang="ts">
  // Erste Einrichtung: Kellerwolke und App-Schlüssel. Nur am Rechner der App, solange nichts eingetragen ist.
  import { einrichtenMit, sitzung } from "../lib/sitzung.svelte";

  const app = $derived(sitzung.app!);
  let adresse = $state("");
  let schluessel = $state("");
  let fehler = $state("");
  let laeuft = $state(false);

  async function los(e: Event) {
    e.preventDefault();
    fehler = "";
    laeuft = true;
    try {
      await einrichtenMit(adresse.trim(), schluessel.trim());
    } catch (f) {
      fehler = (f as Error).message;
    } finally {
      laeuft = false;
    }
  }
</script>

<div class="anmeldung" style="height:100vh; height:100dvh">
  <form class="anmelde-karte" style="width:min(520px, 94vw)" onsubmit={los}>
    <div class="marke"><span class="symbol"><i class="fa-solid {app.symbol}"></i></span> {app.name}</div>
    <div class="rolle"><i class="fa-solid fa-wave-square"></i>erste Einrichtung</div>
    <div class="hinweis-kw">
      <i class="fa-solid fa-cloud"></i>
      <span>Die App hält ihre Dateien in der Kellerwolke, und wer sich anmelden darf, entscheidet ihr App-Schlüssel:
        Anmelden kann das Konto, dem er gehört. Den Schlüssel stellst du in der Kellerwolke unter Einstellungen, Zugänge aus.</span>
    </div>
    <label>Adresse der Kellerwolke<span class="eingabe"><input bind:value={adresse} placeholder="https://192.168.178.49:39280" /></span></label>
    <label>App-Schlüssel<span class="eingabe"><input bind:value={schluessel} placeholder="kw_app_..." autocomplete="off" spellcheck="false" /></span></label>
    {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
    <button class="knopf primaer breit" type="submit" disabled={laeuft || !adresse.trim() || !schluessel.trim()}>
      <i class="fa-solid fa-check"></i> {laeuft ? "Prüft ..." : "Prüfen und einrichten"}
    </button>
    <p class="fassung" style="text-align:center; margin:0">
      Geht nur hier am Rechner. Danach meldest du dich mit dem Konto der Kellerwolke an; alles Weitere unter Einstellungen.
    </p>
  </form>
</div>
