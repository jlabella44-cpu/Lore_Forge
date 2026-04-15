import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

import type { Theme } from "../theme";

export function IntroCard({
  title,
  author,
  theme,
}: {
  title: string;
  author: string;
  theme: Theme;
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleIn = spring({ frame, fps, config: { damping: 18 } });
  const authorFade = interpolate(frame, [fps * 0.3, fps * 0.8], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: theme.background,
        color: theme.text,
        justifyContent: "center",
        alignItems: "center",
        padding: "0 80px",
      }}
    >
      <div
        style={{
          fontFamily: theme.titleFont,
          fontSize: 104,
          lineHeight: 1.05,
          textAlign: "center",
          opacity: titleIn,
          transform: `translateY(${(1 - titleIn) * 20}px)`,
        }}
      >
        {title}
      </div>
      <div
        style={{
          marginTop: 32,
          fontFamily: theme.bodyFont,
          fontSize: 42,
          color: theme.accent,
          opacity: authorFade,
          letterSpacing: 1,
        }}
      >
        {author}
      </div>
    </AbsoluteFill>
  );
}
