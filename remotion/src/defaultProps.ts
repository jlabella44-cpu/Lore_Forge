import type { PackageProps } from "./types";

/**
 * Inline SVG placeholders so Studio runs without any binary assets in the
 * repo. Swap in real image URLs (or backend-rendered paths) at render time.
 */
function placeholder(label: string, bg: string, fg: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920" preserveAspectRatio="xMidYMid slice">
  <rect width="1080" height="1920" fill="${bg}"/>
  <g fill="${fg}" font-family="Georgia, serif" text-anchor="middle">
    <text x="540" y="900" font-size="96" letter-spacing="4">${label}</text>
    <text x="540" y="1020" font-size="42" opacity="0.6">placeholder 9:16</text>
  </g>
</svg>`;
  // URL-encoded data URI — works in both browser (Studio) and Node (render).
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export const DEFAULT_PROPS: PackageProps = {
  tone: "dark",
  title: "The Ghost Orchid",
  author: "David Baldacci",
  cardSeconds: 2,
  images: [
    placeholder("Scene 01", "#1a1a24", "#c2a657"),
    placeholder("Scene 02", "#20202e", "#c2a657"),
    placeholder("Scene 03", "#161620", "#c2a657"),
    placeholder("Scene 04", "#1a1a24", "#c2a657"),
  ],
  durationSeconds: 30,
  // audio + music intentionally omitted so Studio preview is silent.
};
