import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

import { IntroCard } from "./scenes/IntroCard";
import { OutroCard } from "./scenes/OutroCard";
import { CaptionsOverlay } from "./scenes/CaptionsOverlay";
import { THEMES } from "./theme";
import type { ListProps, ListScene } from "./types";

/**
 * LoreForgeList — "Top N Books" list video composition.
 *
 * Like the LoreForge short-hook composition but with variable-length scenes
 * keyed by book title instead of fixed script sections. Each scene shows the
 * book image with a title badge overlay, crossfading between entries.
 */
export const LoreForgeList: React.FC<ListProps> = ({
  tone,
  title,
  author,
  cardSeconds,
  scenes,
  audio,
  music,
  captions,
  durationSeconds,
}) => {
  const { fps } = useVideoConfig();
  const theme = THEMES[tone];

  const cardFrames = Math.round(cardSeconds * fps);
  const totalFrames = Math.round(durationSeconds * fps);

  const sceneTotalFrames = Math.max(
    totalFrames - cardFrames * 2,
    Math.round(fps * 3),
  );

  return (
    <AbsoluteFill style={{ backgroundColor: theme.background }}>
      {/* Intro */}
      <Sequence durationInFrames={cardFrames}>
        <IntroCard title={title} author={author} theme={theme} />
      </Sequence>

      {/* Book scenes — each with title badge */}
      <Sequence from={cardFrames} durationInFrames={sceneTotalFrames}>
        <ListSceneSequence scenes={scenes} theme={theme} totalFrames={sceneTotalFrames} />
      </Sequence>

      {/* Outro */}
      <Sequence
        from={cardFrames + sceneTotalFrames}
        durationInFrames={cardFrames}
      >
        <OutroCard theme={theme} />
      </Sequence>

      {/* Narration starts after intro card */}
      {audio && (
        <Sequence from={cardFrames} durationInFrames={sceneTotalFrames}>
          <Audio src={audio} />
        </Sequence>
      )}

      {/* Background music — runs whole video */}
      {music && <Audio src={music} volume={theme.musicDuckVolume} loop />}

      <Sequence from={cardFrames} durationInFrames={sceneTotalFrames}>
        <CaptionsOverlay
          captions={captions}
          offsetSeconds={0}
          theme={theme}
        />
      </Sequence>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// List scene sequence with book title badges
// ---------------------------------------------------------------------------

function ListSceneSequence({
  scenes,
  theme,
  totalFrames,
}: {
  scenes: ListScene[];
  theme: (typeof THEMES)[keyof typeof THEMES];
  totalFrames: number;
}) {
  const { fps } = useVideoConfig();

  let cursor = 0;
  const placed = scenes.map((scene, index) => {
    const frames = Math.max(1, Math.round(scene.durationSeconds * fps));
    const from = cursor;
    cursor += frames;
    return { scene, index, from, frames };
  });

  // Fill rounding gap: stretch/compress last scene to exactly fill totalFrames
  if (placed.length > 0) {
    const last = placed[placed.length - 1];
    last.frames = totalFrames - last.from;
  }

  return (
    <AbsoluteFill>
      {placed.map(({ scene, index, from, frames }) => (
        <Sequence
          key={`${scene.label}-${index}`}
          from={from}
          durationInFrames={frames}
        >
          <ListSlide
            scene={scene}
            number={index + 1}
            total={scenes.length}
            durationInFrames={frames}
            isFirst={index === 0}
            isLast={index === placed.length - 1}
            theme={theme}
          />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
}

function ListSlide({
  scene,
  number,
  total,
  durationInFrames,
  isFirst,
  isLast,
  theme,
}: {
  scene: ListScene;
  number: number;
  total: number;
  durationInFrames: number;
  isFirst: boolean;
  isLast: boolean;
  theme: (typeof THEMES)[keyof typeof THEMES];
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

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

  // Badge slides up from bottom
  const badgeY = interpolate(frame, [0, Math.round(fps * 0.3)], [40, 0], {
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
      {/* Book title badge at the bottom */}
      <div
        style={{
          position: "absolute",
          bottom: 160,
          left: 40,
          right: 40,
          transform: `translateY(${badgeY}px)`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 8,
        }}
      >
        <div
          style={{
            backgroundColor: "rgba(0,0,0,0.7)",
            borderRadius: 16,
            padding: "16px 32px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 4,
          }}
        >
          <span
            style={{
              color: theme.accent,
              fontSize: 32,
              fontWeight: 700,
              fontFamily: "Georgia, serif",
              letterSpacing: 2,
            }}
          >
            #{number} of {total}
          </span>
          <span
            style={{
              color: "#fff",
              fontSize: 42,
              fontWeight: 700,
              fontFamily: "Georgia, serif",
              textAlign: "center",
              lineHeight: 1.2,
            }}
          >
            {scene.label}
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
}
