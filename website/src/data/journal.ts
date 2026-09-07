export const posts = [
  {
    slug: "count-is-not-rhythm",
    title: "Why the blink count is not enough",
    description:
      "Six blinks can still mean two very different minutes, because what matters is how often you blink and how evenly you do it. That is what the number in the window is trying to show.",
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
      "The sting at four is not only brightness. Attention holds the lids, the tear film waits, and the research on that pause is older than most of the screens we use.",
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
      "Sit as you usually work, turn on EyesRhythm and allow the camera a clear view of your eyes. Here is how.",
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
