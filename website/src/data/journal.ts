export const posts = [
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
