export const posts = [
  {
    slug: "jobs-that-dry-the-eyes",
    title: "The jobs that dry your eyes",
    description:
      "When desk work holds your attention, blink rate falls. These are the jobs that dry the eyes, and what a blink rate detector is for.",
    date: "2026-09-09",
    read: "11 min",
    kicker: "The desk",
    cover: "/images/jobs-cover.jpg",
    coverAlt:
      "A man working at a laptop on a wooden desk, looking at the screen, a webcam visible on the lid.",
  },
  {
    slug: "count-is-not-rhythm",
    title: "Why the blink count is not enough",
    description:
      "A blink counter is not a blink rate detector. Six blinks can still mean two very different minutes, because rate and regularity both matter.",
    date: "2026-09-07",
    read: "7 min",
    kicker: "The score",
    cover: "/images/companion-desk.jpg",
    coverAlt:
      "A laptop open on a wooden desk beside a small blue candle, morning light on an uncluttered workspace.",
  },
  {
    slug: "screens-cut-blink-rate",
    title: "Why screens cut your blink rate",
    description:
      "Screens often cut blink rate in half. Attention holds the lids, the tear film waits, and the research on that pause is older than most of the screens we use.",
    date: "2026-09-04",
    read: "9 min",
    kicker: "The science",
    cover: "/images/blink-cover.jpg",
    coverAlt:
      "Someone sitting still at a laptop by a window, looking at the screen for a long stretch of work.",
  },
  {
    slug: "camera-setup",
    title: "Set up your camera so blinks count",
    description:
      "How to set up a webcam so a blink rate detector can see your eyes. Sit as you usually work, then give the camera a clear view.",
    date: "2026-08-27",
    read: "8 min",
    kicker: "First journal",
    cover: "/images/blog-cover.jpg",
    coverAlt:
      "Someone sitting at a laptop. The camera at the top of the screen can see their face.",
  },
] as const;

export type Post = (typeof posts)[number];

export function getPost(slug: string) {
  return posts.find((post) => post.slug === slug);
}
