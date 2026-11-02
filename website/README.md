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

Keep the GitHub repo **private**.

### Downloads (free)

The app is free. **Download** on the site starts the Mac `.dmg` and the
Windows Setup `.exe` directly. Those files are about 93 MB and 81 MB, which
is over the Cloudflare Pages file limit, so they are not stored in
`website/public`. The links live in `src/config.ts` (`downloads.mac` /
`downloads.windows`).

Do not commit `.zip` / `.dmg` / `.exe` under `website/public`. CI will fail
if you do.

The license gate in the app is off. The Dodo checkout URLs stay in
`src/config.ts` under `dodo` so they can be restored later. They are not
shown on the site.

## Iterate

While `comingSoon` is `true` in `src/config.ts`, every page shows a
single holding screen (no Download, no journal). Set it to `false` and
redeploy when the download links in `src/config.ts` are ready.

| Want to change | File |
|---|---|
| Coming soon / download links, CTA, contact | `src/config.ts` |
| Colors, type | `src/styles/global.css` |
| A section | `src/components/*.astro` |
| Journal | `src/data/journal.ts` and `src/pages/journal/` |
| Security / cache headers | `public/_headers` |

```bash
npm run build
npm run preview
```
