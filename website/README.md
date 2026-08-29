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

Keep the GitHub repo **private**. Do not make a public GitHub Release — that would be a download.

### Payment (keep cards and installers off this site)

Do not put `.zip` / `.dmg` / `.exe` in `website/public`. CI will fail if you do.
`downloadsOpen` in `src/config.ts` stays `false` — installers go out from
Lemon Squeezy, not this origin.

Lemon Squeezy is the single provider: they take the $10, generate a unique
license key, email it to the buyer, store activations, and pay you out.
There is no monthly fee; they take a cut of each sale (currently 5% + 50¢).

When you are ready to take $10:

1. Create a Lemon Squeezy store and two **variants** of the product:
   **EyesRhythm for macOS** and **EyesRhythm for Windows**. Do not put both
   installers on one product — a purchase is one OS.
2. On each variant: enable **license keys**, set **activation limit** to 1
   (or 2 if you want a free reinstall). Attach only that OS’s installer.
3. Copy each variant’s checkout URL into `src/config.ts`
   (`lemonSqueezy.checkoutMac` / `checkoutWindows`).
4. Copy the numeric **store id** and each **variant id** into
   `app/license.py` (`LS_STORE_ID`, `LS_VARIANT_MAC`, `LS_VARIANT_WINDOWS`)
   so the app rejects a key bought for the other OS.
5. Set `comingSoon` to `false` and redeploy.
6. **Get a copy** sends the buyer to Lemon Squeezy. After payment they get
   the key by email. First launch of the app asks for that key (internet
   once). After that the app stays offline.

This origin never sees card numbers (PCI stays with Lemon Squeezy). Do not
load Lemon Squeezy’s overlay script on this site — a plain HTTPS redirect
keeps the marketing page free of third-party JavaScript.

## Iterate

While `comingSoon` is `true` in `src/config.ts`, every page shows a
single holding screen (no Get a copy, no journal). Set it to `false` and
redeploy when the Lemon Squeezy checkout URLs are pasted.

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
