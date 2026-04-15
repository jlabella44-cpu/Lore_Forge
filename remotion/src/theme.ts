import type { Tone } from "./types";

export type Theme = {
  background: string;
  accent: string;
  text: string;
  titleFont: string;
  bodyFont: string;
  /** Volume to duck background music to while narration plays (0..1). */
  musicDuckVolume: number;
  /** "Link in bio" outro line. */
  outroLine: string;
};

/**
 * Tone → visual + audio theme. Fantasy/thriller share "dark", scifi is "hype",
 * romance/historical_fiction share "cozy".
 */
export const THEMES: Record<Tone, Theme> = {
  dark: {
    background: "#0b0b10",
    accent: "#c2a657",
    text: "#f3ecd8",
    titleFont: "'Cormorant Garamond', Georgia, serif",
    bodyFont: "Georgia, serif",
    musicDuckVolume: 0.18,
    outroLine: "Link in bio.",
  },
  hype: {
    background: "#050914",
    accent: "#4af3ff",
    text: "#e6faff",
    titleFont: "'Space Grotesk', 'Helvetica Neue', sans-serif",
    bodyFont: "'Space Grotesk', sans-serif",
    musicDuckVolume: 0.22,
    outroLine: "Link in bio.",
  },
  cozy: {
    background: "#f2ead8",
    accent: "#a65a34",
    text: "#2a1d13",
    titleFont: "'Libre Caslon Text', Georgia, serif",
    bodyFont: "Georgia, serif",
    musicDuckVolume: 0.18,
    outroLine: "Find the link below.",
  },
};
