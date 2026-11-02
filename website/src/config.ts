/**
 * Site copy and knobs, edit here as you iterate.
 *
 * The app is free. Mac and Windows installers are linked below.
 * They are too large for this host, so the buttons download the
 * public files directly. The Dodo checkout URLs stay in ``dodo``
 * so a paid gate can be turned back on without hunting for them.
 * The app itself only asks for a key when the license gate is on.
 */

/** Hold the deployed site to a coming-soon screen. Local `astro dev` ignores this. */
const comingSoonPublic = false;

const MAC_FILE_ID = "1L-S5o-zDXvchb49qCjmAxMatFvO-Rp0P";
const WINDOWS_FILE_ID = "1yAIShWaZTTMQ2_OUoVDVX1cG9BsLrDzV";

function driveDownload(fileId: string): string {
  return `https://drive.usercontent.google.com/download?id=${fileId}&export=download&confirm=t`;
}

export const site = {
  name: "EyesRhythm",
  tagline: "Blink rate detector for long screen days",
  description:
    "EyesRhythm is a free, private webcam blink rate detector for Mac and Windows. It scores how often and how steadily you blink during screen work, and it stays on your computer.",
  url:
    typeof import.meta.env.SITE === "string" && import.meta.env.SITE
      ? String(import.meta.env.SITE).replace(/\/$/, "")
      : "http://localhost:4321",
  contactEmail: "hello@eyesrhythm.com",
  cta: "Download",
  /** False on localhost (`astro dev`) even if the public site is still held. */
  comingSoon: comingSoonPublic && !import.meta.env.DEV,
  /** True: the site offers the Mac and Windows installers directly. */
  downloadsOpen: true,
  price: {
    amount: 0,
    currency: "USD",
    label: "Free",
    cadence: "free",
    updates: "Free for Mac and Windows",
  },
  version: "1.5.0",
  recommendedMachine:
    "Tested on Intel Core i7 and on Mac processors. We recommend this configuration.",
  downloads: {
    mac: {
      href: driveDownload(MAC_FILE_ID),
      file: "EyesRhythm-1.5.0.dmg",
      size: "93 MB",
      label: "macOS",
    },
    windows: {
      href: driveDownload(WINDOWS_FILE_ID),
      file: "EyesRhythm-Setup-1.5.0.exe",
      size: "84 MB",
      label: "Windows",
    },
  },
  /**
   * Unused while the app is free. Kept so checkout can be restored
   * without recreating the Dodo product links.
   */
  dodo: {
    checkoutMac:
      "https://checkout.dodopayments.com/buy/pdt_0Nmc1Cv8LQYff3wqM6ULl?quantity=1",
    checkoutWindows:
      "https://checkout.dodopayments.com/buy/pdt_0Nmc1TZ9g5VKLY81Xi6pG?quantity=1",
  },
} as const;
