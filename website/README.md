# EyeRhythm website

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
5. Optional variable `PUBLIC_SITE_URL` (later your custom domain, e.g. `https://eyerhythm.app`). Until then production is `https://eyerhythm.pages.dev`.
6. Push to `main`, or **Actions → Website → Run workflow**.

Pull requests that touch `website/` get a **preview URL** commented on the PR.

### Custom domain

Cloudflare Pages → project `eyerhythm` → **Custom domains** → add your name
(e.g. `eyerhythm.app`). Then set `PUBLIC_SITE_URL` to that HTTPS origin and
redeploy. Turn on **Always Use HTTPS**.

### Payment (keep cards off this site)

Do not put `.zip` / `.dmg` / `.exe` in `website/public`. CI will fail if you do.

When you are ready to take $10 CAD:

1. Create the product on Lemon Squeezy or Paddle (they take the card).
2. Point **Get a copy** at that checkout URL (HTTPS redirect).
3. Email the license after payment. Do not put the installer on a public URL.

This origin never sees card numbers (PCI stays with the payment provider).

## Iterate

| Want to change | File |
|---|---|
| Price, CTA, contact | `src/config.ts` |
| Colors, type | `src/styles/global.css` |
| A section | `src/components/*.astro` |
| Journal | `src/data/journal.ts` and `src/pages/journal/` |
| Security / cache headers | `public/_headers` |

```bash
npm run build
npm run preview
```
