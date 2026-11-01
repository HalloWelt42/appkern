<script lang="ts">
  // Das Symbol der App in Kopf, Anmeldung und Einrichtung, an einer Stelle: ihr freigestelltes Bild, wenn sie eins hat
  // (symbolbild), sonst ihr Zeichen im Kasten der App-Farbe.
  import type { AppInfo } from "../lib/typen";

  let { app }: { app: AppInfo } = $props();
</script>

{#if app.symbolbild}<img class="symbol-bild" src={app.symbolbild} alt="" />{:else}<span class="symbol"><i class="fa-solid {app.symbol}"></i></span>{/if}
