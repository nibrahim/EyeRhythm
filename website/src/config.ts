/**
 * Site copy and knobs — edit here as you iterate.
 * “Get a copy” is a reservation until a payment provider is wired.
 */
export const site = {
  name: "EyeRhythm",
  tagline: "A quiet rhythm for long screen days",
  description:
    "A private, offline blink companion that turns how often and how steadily you blink into a single, useful rhythm score — so screen days can last longer without the eyes paying first.",
  url:
    typeof import.meta.env.SITE === "string" && import.meta.env.SITE
      ? String(import.meta.env.SITE).replace(/\/$/, "")
      : "http://localhost:4321",
  contactEmail: "",
  cta: "Get a copy",
  price: {
    amount: 10,
    currency: "CAD",
    label: "$10 CAD",
    cadence: "one-time",
    updates: "Feature updates included for six months",
  },
} as const;
