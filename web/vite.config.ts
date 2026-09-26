import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = process.env.FAL_API_ORIGIN ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  // usePolling: sources live on the macOS host and are shared into the VM over virtiofs, which does not deliver
  // inotify events for host-side edits.
  server: { host: "127.0.0.1", port: 5173, watch: { usePolling: true, interval: 300 },
    proxy: { "/api": { target: api, changeOrigin: true } } },
  preview: { host: "127.0.0.1", port: 4173, proxy: { "/api": { target: api, changeOrigin: true } } },
  build: { outDir: "dist", sourcemap: true, chunkSizeWarningLimit: 900 },
});
