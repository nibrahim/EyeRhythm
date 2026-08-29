/**
 * Site copy and knobs — edit here as you iterate.
 * “Get a copy” is a reservation only. Installers are not on this site
 * until payment and licensing are wired.
 */
export const site = {
  name: "EyesRhythm",
  tagline: "A quiet rhythm for long screen days",
  description:
    "A private, offline blink companion that turns how often and how steadily you blink into a single, useful rhythm score — so screen days can last longer without the eyes paying first.",
  url:
    typeof import.meta.env.SITE === "string" && import.meta.env.SITE
      ? String(import.meta.env.SITE).replace(/\/$/, "")
      : "http://localhost:4321",
  contactEmail: "",
  cta: "Get a copy",
  /** Hold the public site to a single coming-soon screen. */
  comingSoon: true,
  /** Keep false until checkout and license keys exist. No public installers. */
  downloadsOpen: false,
  price: {
    amount: 10,
    currency: "USD",
    label: "$10",
    cadence: "one-time",
    updates: "Feature updates included for six months",
  },
} as const;
