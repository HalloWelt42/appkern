import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

// Beim Entwickeln leitet Vite /api ans Backend; im Betrieb liefert das Backend die gebaute Oberfläche selbst aus.
export default defineConfig({
  plugins: [svelte()],
  server: {
    port: __DEVPORT__,
    strictPort: true,
    proxy: { "/api": { target: "http://127.0.0.1:__PORT__", changeOrigin: false } },
  },
});
