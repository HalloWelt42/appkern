<script lang="ts">
  // Erste Seite von __NAME__. Der Probeauftrag zeigt den Ablauf der Aufträge; die eigentlichen Seiten ersetzen sie.
  import { gehe, hole, json, sitzung } from "appkern-oberflaeche";

  let fehler = $state("");
  let laeuft = $state(false);

  async function probe() {
    fehler = "";
    laeuft = true;
    try {
      await hole("/probe", { method: "POST", ...json({ schritte: 20, pause_s: 0.5 }) });
      gehe("auftraege");
    } catch (f) {
      fehler = (f as Error).message;
    } finally {
      laeuft = false;
    }
  }
</script>

<div class="seiten-kopf"><h1>Start</h1></div>
<div class="rollfeld">
  <div class="karte">
    <h2><i class="fa-solid __SYMBOL__"></i>{sitzung.app?.name}</h2>
    <p class="karte-unter">{sitzung.app?.name} {sitzung.app?.rolle}. Angemeldet als {sitzung.konto?.name}.</p>
    <div class="feld">
      <div class="was">
        <div class="name">Probeauftrag</div>
        <div class="beschreibung">Zwanzig Schritte mit Pause: zeigt Phasen, Fortschritt, Abbrechen und Wiederholen.</div>
      </div>
      <button class="knopf primaer" onclick={probe} disabled={laeuft}><i class="fa-solid fa-play"></i> Starten</button>
    </div>
    {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
  </div>
</div>
