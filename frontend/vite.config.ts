/**
 * Vite build settings for the React dashboard
 * ===========================================
 *
 * * `npm run dev`  — hot-reload UI on port 5173. `/api` and `/ws` are
 *   forwarded to the Python engine on 8742 so you do not need two origins.
 * * `npm run build` — writes a static site into `frontend/dist`, which the
 *   packaged desktop app then serves.
 */
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    fs: {
      allow: [path.resolve(rootDir, "..")],
    },
    proxy: {
      "/api": "http://127.0.0.1:8742",
      "/alert.mp3": "http://127.0.0.1:8742",
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
    rollupOptions: {
      input: path.resolve(rootDir, "index.html"),
    },
  },
});
