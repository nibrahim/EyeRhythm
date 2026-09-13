import type { APIRoute } from "astro";

export const GET: APIRoute = ({ site }) => {
  const sitemap = new URL("sitemap-index.xml", site ?? "https://eyesrhythm.com");
  const body = `User-agent: *
Allow: /

# Paid app files are not on this site.
Disallow: /downloads/

Sitemap: ${sitemap.href}
`;
  return new Response(body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
};
