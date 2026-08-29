/**
 * Site copy and knobs — edit here as you iterate.
 *
 * Installers are never hosted here. After you create the two Lemon Squeezy
 * products (macOS and Windows), paste their checkout URLs below and set
 * ``comingSoon`` to false.
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
  /** Keep false — installers go out from Lemon Squeezy, not this origin. */
  downloadsOpen: false,
  price: {
    amount: 10,
    currency: "USD",
    label: "$10",
    cadence: "one-time",
    updates: "Feature updates included for six months",
  },
  /**
   * Lemon Squeezy buy links (Share → Checkout URL) for each OS variant.
   * Leave empty until the store products exist. Never put both OS files
   * on one product — a purchase is Mac or Windows, not both.
   */
  lemonSqueezy: {
    checkoutMac: "",
    checkoutWindows: "",
  },
} as const;

export function checkoutUrl(platform: "mac" | "windows"): string {
  const url =
    platform === "mac"
      ? site.lemonSqueezy.checkoutMac
      : site.lemonSqueezy.checkoutWindows;
  return /^https:\/\//i.test(url) ? url : "";
}

export function checkoutReady(): boolean {
  return Boolean(checkoutUrl("mac") && checkoutUrl("windows"));
}
