import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

import type { Theme } from "../theme";

export function OutroCard({ theme }: { theme: Theme }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeIn = interpolate(frame, [0, fps * 0.4], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: theme.background,
        color: theme.accent,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          fontFamily: theme.titleFont,
          fontSize: 96,
          opacity: fadeIn,
          letterSpacing: 2,
        }}
      >
        {theme.outroLine}
      </div>
    </AbsoluteFill>
  );
}
