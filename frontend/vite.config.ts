/**
 * Vite build settings for the React dashboard
 * ===========================================
 *
 * * `npm run dev`  — hot-reload UI on port 5173. `/api` and `/ws` are
 *   forwarded to the Python engine on 8742 so you do not need two origins.
 * * `npm run build` — writes a static site into `frontend/dist`, which the
 *   packaged desktop app then serves.
 */
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8742",
      "/ws": {
        target: "ws://127.0.0.1:8742",
        ws: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
    assetsDir: "assets",
  },
});
