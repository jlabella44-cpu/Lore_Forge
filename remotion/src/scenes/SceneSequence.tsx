import { AbsoluteFill, Img, Sequence, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

import type { Scene } from "../types";

/**
 * Lays out each scene back-to-back for exactly its `durationSeconds`, with a
 * short crossfade at each boundary and a subtle Ken Burns zoom across the
 * scene's hold time.
 */
export function SceneSequence({ scenes }: { scenes: Scene[] }) {
  const { fps } = useVideoConfig();

  let cursor = 0;
  const placed = scenes.map((scene, index) => {
    const frames = Math.max(1, Math.round(scene.durationSeconds * fps));
    const from = cursor;
    cursor += frames;
    return { scene, index, from, frames };
  });

  return (
    <AbsoluteFill>
      {placed.map(({ scene, index, from, frames }) => (
        <Sequence
          key={`${scene.section}-${index}`}
          from={from}
          durationInFrames={frames}
        >
          <SceneSlide
            scene={scene}
            durationInFrames={frames}
            isFirst={index === 0}
            isLast={index === placed.length - 1}
          />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
}

function SceneSlide({
  scene,
  durationInFrames,
  isFirst,
  isLast,
}: {
  scene: Scene;
  durationInFrames: number;
  isFirst: boolean;
  isLast: boolean;
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Crossfade ~0.4s into and out of the slide, unless it's the first/last
  // (which sit against the intro/outro cards and don't fade internally).
  const fadeFrames = Math.min(
    Math.round(fps * 0.4),
    Math.floor(durationInFrames / 2),
  );

  const opacity = (() => {
    if (frame < fadeFrames && !isFirst) {
      return interpolate(frame, [0, fadeFrames], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
    }
    if (frame > durationInFrames - fadeFrames && !isLast) {
      return interpolate(
        frame,
        [durationInFrames - fadeFrames, durationInFrames],
        [1, 0],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
      );
    }
    return 1;
  })();

  const zoom = interpolate(frame, [0, durationInFrames], [1.0, 1.08], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ opacity }}>
      <Img
        src={scene.image}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${zoom})`,
        }}
      />
    </AbsoluteFill>
  );
}
