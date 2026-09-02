/**
 * Site copy and knobs, edit here as you iterate.
 *
 * Installers are never hosted here. Checkout URLs live in ``dodo`` below.
 * Set ``comingSoonPublic`` to true only if the public store must hide again.
 */

/** Hold the deployed site to a coming-soon screen. Local `astro dev` ignores this. */
const comingSoonPublic = false;

export const site = {
  name: "EyesRhythm",
  tagline: "A quiet rhythm for long screen days",
  description:
    "A private, offline blink companion that turns how often and how steadily you blink into a single, useful rhythm score, so screen days can last longer without the eyes paying first.",
  url:
    typeof import.meta.env.SITE === "string" && import.meta.env.SITE
      ? String(import.meta.env.SITE).replace(/\/$/, "")
      : "http://localhost:4321",
  contactEmail: "hello@eyesrhythm.com",
  cta: "Get a copy",
  /** False on localhost (`astro dev`) even if the public site is still held. */
  comingSoon: comingSoonPublic && !import.meta.env.DEV,
  /** Keep false, installers go out from Dodo Payments, not this origin. */
  downloadsOpen: false,
  price: {
    amount: 12,
    currency: "USD",
    label: "$12",
    cadence: "one-time",
    updates: "Feature updates included for lifetime",
  },
  recommendedMachine:
    "Tested on Intel Core i7 and on Mac processors. We recommend this configuration.",
  /**
   * Dodo Payments buy links (product → payment link / checkout URL)
   * for each OS. Leave empty until the products exist. Never put both
   * OS files on one product, a purchase is Mac or Windows, not both.
   */
  dodo: {
    checkoutMac:
      "https://checkout.dodopayments.com/buy/pdt_0Nmc1Cv8LQYff3wqM6ULl?quantity=1",
    checkoutWindows:
      "https://checkout.dodopayments.com/buy/pdt_0Nmc1TZ9g5VKLY81Xi6pG?quantity=1",
  },
} as const;

export function checkoutUrl(platform: "mac" | "windows"): string {
  const url =
    platform === "mac" ? site.dodo.checkoutMac : site.dodo.checkoutWindows;
  return /^https:\/\//i.test(url) ? url : "";
}

export function checkoutReady(): boolean {
  return Boolean(checkoutUrl("mac") && checkoutUrl("windows"));
}
