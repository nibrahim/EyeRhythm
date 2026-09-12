import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

const site = process.env.PUBLIC_SITE_URL || "http://localhost:4321";

// Static site: `npm run build` writes HTML/CSS/JS to dist/.
// Hosted on Cloudflare Pages from GitHub Actions.
export default defineConfig({
  site,
  integrations: [
    sitemap({
      filter: (page) => !page.includes("/404"),
      serialize(item) {
        const url = item.url.replace(/\/$/, "");
        if (url === site) {
          item.changefreq = "weekly";
          item.priority = 1;
        } else if (url.endsWith("/blink-rate-detector")) {
          item.changefreq = "weekly";
          item.priority = 0.9;
        } else if (url.includes("/journal")) {
          item.changefreq = "monthly";
          item.priority = 0.8;
        }
        return item;
      },
    }),
  ],
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
