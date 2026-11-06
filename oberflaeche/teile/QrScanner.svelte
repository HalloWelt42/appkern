<script lang="ts">
  // QR-Code mit der Kamera lesen (KW-2; Abschrift des Bausteins der Kellerwolke, frontend/src/lib/QrScanner.svelte,
  // Entwurf dort mockups/qr-einrichten.html): bildschirmfüllend, Rahmen in der Mitte,
  // unten Abbrechen und ein zweiter Weg (etwa Code eintippen). Die Kamera gibt der Browser nur über https frei;
  // gelesen wird mit qr-scanner (nutzt den eingebauten Leser des Browsers, sonst einen eigenen, auch am iPhone).
  // `gelesen` prüft den Text: null heißt angenommen (der Aufrufer schließt), ein Text ist der Grund zum Weitersuchen.
  import { onMount } from "svelte";
  import QrScanner from "qr-scanner";

  interface Props {
    hinweis: string;
    gelesen: (text: string) => string | null | Promise<string | null>;
    abbrechen: () => void;
    anders?: { text: string; icon: string; tun: () => void } | null;
  }
  let { hinweis, gelesen, abbrechen, anders = null }: Props = $props();

  let video = $state<HTMLVideoElement | null>(null);
  let meldung = $state("");
  let erkannt = $state(false);
  let pruefend = false;

  function kameraFehler(f: unknown): string {
    const name = (f as { name?: string })?.name ?? String(f);
    if (!window.isSecureContext) return "Die Kamera geht nur über https.";
    if (/NotAllowed|Permission/i.test(name)) return "Die Kamera ist nicht erlaubt. Erlaube sie in den Einstellungen des Browsers.";
    if (/NotFound|no camera/i.test(name)) return "Dieses Gerät hat keine Kamera.";
    return "Die Kamera ließ sich nicht starten.";
  }

  onMount(() => {
    if (!video) return;
    const leser = new QrScanner(
      video,
      async (ergebnis) => {
        if (pruefend || erkannt) return;
        pruefend = true;
        try {
          const grund = await gelesen(ergebnis.data);
          if (grund === null) {
            erkannt = true;
            leser.stop();
          } else {
            meldung = grund;
          }
        } finally {
          pruefend = false;
        }
      },
      { preferredCamera: "environment", highlightScanRegion: false, maxScansPerSecond: 8, returnDetailedScanResult: true },
    );
    leser.start().catch((f) => (meldung = kameraFehler(f)));
    return () => {
      leser.stop();
      leser.destroy();
    };
  });

  function taste(e: KeyboardEvent) {
    if (e.key === "Escape") abbrechen();
  }
</script>

<svelte:window onkeydown={taste} />

<div class="qr-scanner" class:ok={erkannt} role="dialog" aria-modal="true" aria-label="QR-Code scannen">
  <!-- svelte-ignore a11y_media_has_caption -->
  <video bind:this={video} playsinline muted></video>
  <div class="rahmen" aria-hidden="true"></div>
  <p class="text" role="status">{meldung || (erkannt ? "Erkannt" : hinweis)}</p>
  <div class="unten">
    <button type="button" onclick={abbrechen}><i class="fa-solid fa-xmark"></i> Abbrechen</button>
    {#if anders}
      <button type="button" onclick={anders.tun}><i class="fa-solid {anders.icon}"></i> {anders.text}</button>
    {/if}
  </div>
</div>

<style>
  /* Die Kamera ist immer dunkel: Grund aus der Schattenfarbe, Rahmen und Schrift im Licht, erkannt in Gut */
  .qr-scanner { position: fixed; inset: 0; z-index: 90; background: var(--schattenfarbe); display: grid; place-items: center; overflow: hidden; }
  video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .rahmen { position: relative; width: min(64vw, 260px); aspect-ratio: 1; border-radius: 22px; border: 4px solid var(--licht);
            box-shadow: 0 0 0 200vmax color-mix(in srgb, var(--schattenfarbe) 45%, transparent); }
  .ok .rahmen { border-color: var(--gut); }
  .text { position: absolute; left: 24px; right: 24px; bottom: calc(110px + env(safe-area-inset-bottom)); margin: 0; text-align: center;
          color: var(--licht); font-size: var(--titel); text-shadow: 0 1px 3px color-mix(in srgb, var(--schattenfarbe) 60%, transparent); }
  .unten { position: absolute; left: 0; right: 0; bottom: calc(30px + env(safe-area-inset-bottom)); display: flex; justify-content: center; gap: 14px; flex-wrap: wrap; padding: 0 16px; }
  .unten button { height: 48px; padding: 0 20px; border-radius: 24px; border: none; background: color-mix(in srgb, var(--licht) 18%, transparent);
                  color: var(--licht); font: inherit; font-size: var(--gross); display: inline-flex; align-items: center; gap: 8px; cursor: pointer; }
</style>
