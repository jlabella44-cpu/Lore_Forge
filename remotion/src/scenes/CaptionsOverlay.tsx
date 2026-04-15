import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";

import type { CaptionWord } from "../types";
import type { Theme } from "../theme";

/**
 * Rolling 3-4 word captions anchored to the lower third. The narration
 * (Audio) starts `offsetSeconds` into the video — intro card time — so we
 * add that to the current frame's seconds before matching caption windows.
 *
 * The matched word is highlighted with the theme accent; surrounding words
 * sit at reduced opacity. Non-matching stretches (brief pauses between
 * words) keep the last matched window visible until the next word starts,
 * so short gaps don't blank the overlay.
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
  if (nowSeconds < 0 || nowSeconds > (captions[captions.length - 1]?.end ?? 0) + 0.5) {
    return null;
  }

  const activeIndex = findActiveIndex(captions, nowSeconds);
  if (activeIndex < 0) return null;

  const WINDOW = 3; // words before + after
  const start = Math.max(0, activeIndex - WINDOW);
  const end = Math.min(captions.length, activeIndex + WINDOW + 1);
  const window = captions.slice(start, end);
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
          lineHeight: 1.15,
          fontWeight: 700,
          padding: "18px 28px",
          borderRadius: 14,
          backgroundColor: "rgba(0, 0, 0, 0.55)",
          color: "#ffffff",
          textShadow: "0 2px 12px rgba(0,0,0,0.6)",
          letterSpacing: 0.3,
        }}
      >
        {window.map((w, i) => (
          <span
            key={`${w.start}-${i}`}
            style={{
              color: i === activeWithinWindow ? theme.accent : "#ffffff",
              opacity: i === activeWithinWindow ? 1 : 0.75,
              marginRight: 12,
            }}
          >
            {w.word.trim()}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
}

function findActiveIndex(captions: CaptionWord[], nowSeconds: number): number {
  // Linear scan is fine — 90-sec short has ~200 words max. If this ever
  // grows, binary search by `start`.
  for (let i = 0; i < captions.length; i++) {
    const w = captions[i];
    if (nowSeconds >= w.start && nowSeconds <= w.end) return i;
    if (nowSeconds < w.start) {
      // We're between words. Keep the previous one visible briefly.
      return Math.max(0, i - 1);
    }
  }
  return captions.length - 1;
}
