# EyesRhythm website

Static Astro site. No server, no database, no analytics. Hosted on
**Cloudflare Pages**, built and shipped by **GitHub Actions**.

## Run locally

```bash
cd website
npm install
npm run dev
```

Open [http://localhost:4321](http://localhost:4321).

## Launch (Cloudflare + GitHub Actions)

1. Create a free Cloudflare account: [dash.cloudflare.com](https://dash.cloudflare.com/sign-up).
2. In Cloudflare: **Workers & Pages** → copy **Account ID** (right sidebar).
3. In Cloudflare: **My Profile → API Tokens → Create Token**.
   Use the **Edit Cloudflare Pages** template (Account · Cloudflare Pages · Edit, plus Account Settings · Read).
4. In GitHub: **Settings → Secrets and variables → Actions**:
   - Secret `CLOUDFLARE_API_TOKEN`
   - Secret `CLOUDFLARE_ACCOUNT_ID`
5. Variable `PUBLIC_SITE_URL` = `https://eyesrhythm.com`.
6. Push to `main`, or **Actions → Website → Run workflow**.

Pull requests that touch `website/` get a **preview URL** commented on the PR.

### Custom domain (`eyesrhythm.com`)

Apex domains on Pages need the domain as a Cloudflare zone:

1. Cloudflare dashboard → **Add a site** → `eyesrhythm.com` (Free plan is enough).
2. Copy the two Cloudflare nameservers it shows.
3. At the registrar where you bought the domain: replace nameservers with those two. Do not add a CNAME at the registrar for the root domain.
4. Wait until Cloudflare says the zone is **Active** (often minutes; can take up to 24–48 hours).
5. **Workers & Pages** → project `eyerhythm` → **Custom domains** → **Set up a domain** → `eyesrhythm.com`.
6. Optional: also add `www.eyesrhythm.com`, then in the zone DNS add a redirect from `www` to `https://eyesrhythm.com`.
7. Turn on **Always Use HTTPS**. SSL is issued automatically.
8. GitHub → **Settings → Secrets and variables → Actions → Variables** → `PUBLIC_SITE_URL` = `https://eyesrhythm.com`.
9. **Actions → Website → Run workflow** (or push) so canonical URLs match.

## Search (Google)

The marketing site is only findable after Google crawls it. On-page copy
names “blink rate detector”; a sitemap is emitted at `/sitemap-index.xml`.
That is not enough by itself:

1. [Google Search Console](https://search.google.com/search-console) →
   **Add property** → `https://eyesrhythm.com`.
2. Verify with a DNS TXT record on the Cloudflare zone (fastest), or by
   uploading the HTML file Google gives you into `website/public/`.
3. **Sitemaps** → submit `https://eyesrhythm.com/sitemap-index.xml`.
4. **URL inspection** → `https://eyesrhythm.com/blink-rate-detector` →
   **Request indexing**. Repeat for the home page.
5. In Cloudflare: turn **Bot Fight Mode** off, or at least allow verified
   search crawlers. The free Bot Fight feature often blocks Googlebot, which
   is why a new site can stay invisible.

Indexing a new domain often takes days to a few weeks. Rankings need
links from other sites as well as this copy.

Keep the GitHub repo **private**. Do not make a public GitHub Release — that would be a download.

### Payment (keep cards and installers off this site)

Do not put `.zip` / `.dmg` / `.exe` in `website/public`. CI will fail if you do.
`downloadsOpen` in `src/config.ts` stays `false` — installers go out from
Dodo Payments, not this origin.

Dodo Payments is the single provider: they take the $12, generate a unique
license key, email it to the buyer, store activations, and pay you out to
an Indian bank account. There is no monthly fee; they take a cut of each
sale (currently about 4% + 40¢, plus 1.5% on international cards).

When you are ready to take $12:

1. Create a Dodo Payments account as **India** (PAN + Indian bank in your
   name). Do not register as Canada.
2. Create two **products**: **EyesRhythm for macOS** and **EyesRhythm for
   Windows**. Do not put both installers on one product — a purchase is
   one OS.
3. On each product: enable **license keys**, set **activation limit** to 1
   (or 2 if you want a free reinstall). Attach only that OS’s installer.
   Price each at **$12 USD**.
4. Copy each product’s checkout / payment-link URL into `src/config.ts`
   (`dodo.checkoutMac` / `checkoutWindows`).
5. Copy each product id (`pdt_…`) into `app/license.py`
   (`DODO_PRODUCT_MAC`, `DODO_PRODUCT_WINDOWS`) so the app rejects a key
   bought for the other OS.
6. Set `comingSoon` to `false` and redeploy.
7. **Get a copy** sends the buyer to Dodo. After payment they get the key
   by email. First launch of the app asks for that key (internet once).
   After that the app stays offline.

This origin never sees card numbers (PCI stays with Dodo). Do not load a
checkout overlay script on this site — a plain HTTPS redirect keeps the
marketing page free of third-party JavaScript.

## Iterate

While `comingSoon` is `true` in `src/config.ts`, every page shows a
single holding screen (no Get a copy, no journal). Set it to `false` and
redeploy when the Dodo Payments checkout URLs are pasted.

| Want to change | File |
|---|---|
| Coming soon / price, CTA, contact | `src/config.ts` |
| Colors, type | `src/styles/global.css` |
| A section | `src/components/*.astro` |
| Journal | `src/data/journal.ts` and `src/pages/journal/` |
| Security / cache headers | `public/_headers` |

```bash
npm run build
npm run preview
```
