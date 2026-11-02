export const faqs = [
  {
    q: "What is a blink rate detector?",
    a: "A blink rate detector uses a camera to notice each blink and measure how often they happen, usually as blinks per minute. EyesRhythm does that on your Mac or Windows computer, then also looks at how evenly those blinks are spaced.",
  },
  {
    q: "Does EyesRhythm work with a laptop webcam?",
    a: "Yes. It uses the built-in camera on a Mac or Windows laptop, or a USB webcam. Sit as you usually work so the camera can see your eyes. The setup guide in the journal walks through the few things that help.",
  },
  {
    q: "Does any video leave my computer?",
    a: "No. Frames are read on this machine and discarded. There is no account, no license key, no cloud, and no analytics. Camera frames are not uploaded or kept as a film of your face.",
  },
  {
    q: "How is this different from a blink counter?",
    a: "A counter only totals blinks. Six blinks can still mean two very different minutes if they arrive in clumps with a long dry wait in the middle. EyesRhythm folds rate and regularity into one Ocular Rhythm Index, from 0 to 100.",
  },
  {
    q: "What is Poise for?",
    a: "Poise shows which way you turned your head today, in 30° slices. Green is where you looked most. Red is a direction you barely used. Long computer work parks the neck in one pose. Poise is there so you move it up, down, left, and right from time to time, which lets the neck and shoulders relax, then you look back at the screen. It is a reminder, not a treatment.",
  },
  {
    q: "Is EyesRhythm a medical device?",
    a: "No. It is a wellness companion for desk work, not a diagnosis or a treatment. Lasting discomfort or a change in vision belongs with an eye-care professional.",
  },
] as const;

export function faqJsonLd() {
  return {
    "@type": "FAQPage",
    mainEntity: faqs.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.a,
      },
    })),
  };
}
