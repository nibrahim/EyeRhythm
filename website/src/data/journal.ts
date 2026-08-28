export const posts = [
  {
    slug: "camera-setup",
    title: "Set up your camera so blinks count",
    description:
      "Sit as you usually work, turn the camera on, and give EyeRhythm a clear view of your eyes. Here is how.",
    date: "2026-08-27",
    read: "8 min",
    kicker: "First journal",
  },
] as const;

export type Post = (typeof posts)[number];

export function getPost(slug: string) {
  return posts.find((post) => post.slug === slug);
}
