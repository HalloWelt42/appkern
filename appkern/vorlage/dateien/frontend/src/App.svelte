<script lang="ts">
  // Die Bereiche von __NAME__ in der gemeinsamen Schale (Kopf, Navigation, Aufträge, Protokoll, Einstellungen).
  import { Schale, type Bereich } from "appkern-oberflaeche";
  import Start from "./seiten/Start.svelte";

  const bereiche: Bereich[] = [{ schluessel: "start", titel: "Start", symbol: "fa-house", seite: Start, reiter: true }];
</script>

<Schale {bereiche} fassung={__APP_FASSUNG__} />
