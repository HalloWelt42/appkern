<script lang="ts">
  // Die Kellerwolke führt den Browser mit einer Anfrage hierher (/anfrage/<id>, Dateimenü "In ... öffnen"): annehmen,
  // dann sagt die App, welche ihrer Ansichten die Datei zeigt, und es geht dorthin (ohne neuen Eintrag im Verlauf).
  import { onMount } from "svelte";
  import { anfrageOeffnen } from "../lib/kellerwolke";
  import { gehe, navigation } from "../lib/navigation.svelte";
  import { sitzung } from "../lib/sitzung.svelte";
  import type { Anfrage } from "../lib/typen";

  let { oeffnen }: { oeffnen: (a: Anfrage) => Promise<string> | string } = $props();
  let fehler = $state("");

  onMount(() => {
    const id = navigation.teile[0] ?? "";
    void (async () => {
      try {
        gehe(await oeffnen(await anfrageOeffnen(id)), true);
      } catch (f) {
        fehler = (f as Error).message;
      }
    })();
  });
</script>

<div class="laden-mitte">
  {#if fehler}
    <div class="leer-gross">
      <i class="fa-solid fa-cloud"></i>
      <h2>Diese Datei lässt sich so nicht mehr öffnen</h2>
      <p>{fehler}. Öffne sie erneut aus der Kellerwolke; dann gilt das Recht der App wieder für diese Datei.</p>
      {#if sitzung.app?.kellerwolke}<a class="knopf primaer" href={sitzung.app.kellerwolke}><i class="fa-solid fa-cloud"></i> Zur Kellerwolke</a>{/if}
    </div>
  {:else}
    <p class="leer"><i class="fa-solid fa-circle-notch fa-spin"></i> Wird aus der Kellerwolke geöffnet ...</p>
  {/if}
</div>
