import { defineConfig } from "astro/config";

const site = process.env.PUBLIC_SITE_URL || "http://localhost:4321";

// Static site: `npm run build` writes HTML/CSS/JS to dist/.
// Hosted on Cloudflare Pages from GitHub Actions.
export default defineConfig({
  site,
  output: "static",
  trailingSlash: "never",
  compressHTML: true,
  prefetch: true,
  server: {
    port: 4321,
  },
  vite: {
    build: {
      assetsInlineLimit: 0,
    },
    css: {
      devSourcemap: true,
    },
  },
});
