import type { PackageProps, Section } from "./types";

/**
 * Inline SVG placeholders so Studio runs without any binary assets in the
 * repo. Real renders pass absolute local paths from the backend; Studio
 * sees these `data:image/svg+xml` URLs directly.
 */
function placeholder(label: string, bg: string, fg: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920" preserveAspectRatio="xMidYMid slice">
  <rect width="1080" height="1920" fill="${bg}"/>
  <g fill="${fg}" font-family="Georgia, serif" text-anchor="middle">
    <text x="540" y="900" font-size="96" letter-spacing="4">${label}</text>
    <text x="540" y="1020" font-size="42" opacity="0.6">placeholder 9:16</text>
  </g>
</svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

const PLACEHOLDER_SECTIONS: ReadonlyArray<{
  section: Section;
  label: string;
  durationSeconds: number;
}> = [
  { section: "hook", label: "Hook", durationSeconds: 4 },
  { section: "world_tease", label: "World", durationSeconds: 7 },
  { section: "emotional_pull", label: "Emotion", durationSeconds: 8 },
  { section: "social_proof", label: "Proof", durationSeconds: 5 },
  { section: "cta", label: "CTA", durationSeconds: 3 },
];

const PLACEHOLDER_CAPTIONS = [
  { word: "Once", start: 0.1, end: 0.5 },
  { word: "every", start: 0.6, end: 0.9 },
  { word: "century", start: 1.0, end: 1.6 },
  { word: "the", start: 1.7, end: 1.9 },
  { word: "orchid", start: 2.0, end: 2.6 },
  { word: "blooms.", start: 2.7, end: 3.3 },
];

export const DEFAULT_PROPS: PackageProps = {
  tone: "dark",
  title: "The Ghost Orchid",
  subtitle: "David Baldacci",
  cardSeconds: 2,
  scenes: PLACEHOLDER_SECTIONS.map(({ section, label, durationSeconds }) => ({
    section,
    image: placeholder(label, "#1a1a24", "#c2a657"),
    durationSeconds,
  })),
  captions: PLACEHOLDER_CAPTIONS,
  durationSeconds:
    PLACEHOLDER_SECTIONS.reduce((a, s) => a + s.durationSeconds, 0) + 4,
  // audio + music intentionally omitted so Studio preview is silent.
};
