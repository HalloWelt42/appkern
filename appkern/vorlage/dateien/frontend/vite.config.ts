import { readFileSync } from "node:fs";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

// Fassung der gebauten Oberfläche (aus version.json): eingebaut ins Skript und als Meta in die Startseite. Der Server
// meldet die der ausgelieferten Startseite; weicht sie ab, lädt ein offener Tab von selbst neu.
const FASSUNG = JSON.parse(readFileSync(new URL("../version.json", import.meta.url), "utf-8")).version as string;
const fassungEinsetzen = {
  name: "fassung-einsetzen",
  transformIndexHtml: (html: string) => html.replace("</head>", `  <meta name="app-fassung" content="${FASSUNG}" />\n  </head>`),
};

// Beim Entwickeln leitet Vite /api ans Backend; im Betrieb liefert das Backend die gebaute Oberfläche selbst aus.
export default defineConfig({
  plugins: [svelte(), fassungEinsetzen],
  define: { __APP_FASSUNG__: JSON.stringify(FASSUNG) },
  server: {
    port: __DEVPORT__,
    strictPort: true,
    proxy: { "/api": { target: "http://127.0.0.1:__PORT__", changeOrigin: false } },
  },
});
