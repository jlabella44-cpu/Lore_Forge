import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";

import type { CaptionWord } from "../types";
import type { Theme } from "../theme";

/**
 * Word-synced captions in the lower third.
 *
 * - Rolling 6-word window (3 before + 3 after the active word).
 * - Active word pops in with a spring on first appearance and stays
 *   larger + accent-colored while it's playing.
 * - "Power words" (numbers, currency, ordinals, proper-noun tail
 *   punctuation like "!", and standalone ALL-CAPS tokens) are rendered
 *   bold so the line-by-line rhythm of short-form voiceover scans at
 *   a glance. Cheap heuristic — no per-video tuning.
 *
 * Between-word micro-pauses keep the last matched window visible until
 * the next word starts, so short gaps don't blank the overlay.
 */
export function CaptionsOverlay({
  captions,
  offsetSeconds,
  theme,
}: {
  captions: CaptionWord[];
  offsetSeconds: number;
  theme: Theme;
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (captions.length === 0) return null;

  const nowSeconds = frame / fps - offsetSeconds;
  const lastEnd = captions[captions.length - 1]?.end ?? 0;
  if (nowSeconds < 0 || nowSeconds > lastEnd + 0.5) return null;

  const activeIndex = findActiveIndex(captions, nowSeconds);
  if (activeIndex < 0) return null;

  const WINDOW = 3;
  const start = Math.max(0, activeIndex - WINDOW);
  const end = Math.min(captions.length, activeIndex + WINDOW + 1);
  const windowWords = captions.slice(start, end);
  const activeWithinWindow = activeIndex - start;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 260,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          maxWidth: "82%",
          textAlign: "center",
          fontFamily: theme.bodyFont,
          fontSize: 64,
          lineHeight: 1.18,
          fontWeight: 700,
          padding: "22px 32px",
          borderRadius: 16,
          backgroundColor: "rgba(0, 0, 0, 0.58)",
          color: "#ffffff",
          textShadow: "0 2px 14px rgba(0,0,0,0.65)",
          letterSpacing: 0.3,
        }}
      >
        {windowWords.map((w, i) => {
          const isActive = i === activeWithinWindow;
          const absoluteIndex = start + i;
          return (
            <Word
              key={`${absoluteIndex}-${w.start}`}
              word={w.word.trim()}
              isActive={isActive}
              isPower={isPowerWord(w.word)}
              accent={theme.accent}
              popKey={absoluteIndex}
            />
          );
        })}
      </div>
    </AbsoluteFill>
  );
}

function Word({
  word,
  isActive,
  isPower,
  accent,
  popKey,
}: {
  word: string;
  isActive: boolean;
  isPower: boolean;
  accent: string;
  popKey: number;
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Spring only when the word is active, keyed on popKey so re-mounts
  // don't re-trigger the pop.
  const pop = isActive
    ? spring({ frame, fps, config: { damping: 15, stiffness: 180 } })
    : 1;
  const scale = isActive ? 1 + pop * 0.08 : 1;

  return (
    <span
      style={{
        display: "inline-block",
        marginRight: 14,
        color: isActive ? accent : "#ffffff",
        opacity: isActive ? 1 : 0.6,
        fontWeight: isPower ? 900 : 700,
        transform: `scale(${scale})`,
        transformOrigin: "center",
        transition: "color 80ms linear",
      }}
    >
      {word}
    </span>
  );
}

/** Numbers, currency, ordinals, standalone ALL-CAPS, or terminal-punct'd
 *  words ("unforgettable!") — cheap "power word" heuristic. */
function isPowerWord(raw: string): boolean {
  const w = raw.trim();
  if (!w) return false;
  if (/[\d$€£¥%]/.test(w)) return true;             // numbers, currency, percent
  if (/[!?]$/.test(w)) return true;                   // ends with ! / ?
  const bare = w.replace(/[^A-Za-z]/g, "");
  if (bare.length >= 3 && bare === bare.toUpperCase()) return true; // ALL CAPS
  return false;
}

function findActiveIndex(captions: CaptionWord[], nowSeconds: number): number {
  for (let i = 0; i < captions.length; i++) {
    const w = captions[i];
    if (nowSeconds >= w.start && nowSeconds <= w.end) return i;
    if (nowSeconds < w.start) return Math.max(0, i - 1);
  }
  return captions.length - 1;
}
