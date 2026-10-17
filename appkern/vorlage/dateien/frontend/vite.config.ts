import { readFileSync } from "node:fs";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

// Fassung der gebauten Oberfläche (aus version.json); meldet der Server eine andere, lädt die Seite von selbst neu.
const FASSUNG = JSON.parse(readFileSync(new URL("../version.json", import.meta.url), "utf-8")).version as string;

// Beim Entwickeln leitet Vite /api ans Backend; im Betrieb liefert das Backend die gebaute Oberfläche selbst aus.
export default defineConfig({
  plugins: [svelte()],
  define: { __APP_FASSUNG__: JSON.stringify(FASSUNG) },
  server: {
    port: __DEVPORT__,
    strictPort: true,
    proxy: { "/api": { target: "http://127.0.0.1:__PORT__", changeOrigin: false } },
  },
});
