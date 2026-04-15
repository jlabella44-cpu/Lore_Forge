import { AbsoluteFill, Audio, Sequence, useVideoConfig } from "remotion";

import { IntroCard } from "./scenes/IntroCard";
import { OutroCard } from "./scenes/OutroCard";
import { SceneSequence } from "./scenes/SceneSequence";
import { CaptionsOverlay } from "./scenes/CaptionsOverlay";
import { THEMES } from "./theme";
import type { PackageProps } from "./types";

export const LoreForge: React.FC<PackageProps> = ({
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

  // The scenes' own durations already sum to narration length. We pad
  // intro + outro cards on top.
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

      {/* Scene sequence — one image per script section, each held for its
          proportional share of narration time */}
      <Sequence from={cardFrames} durationInFrames={sceneTotalFrames}>
        <SceneSequence scenes={scenes} />
      </Sequence>

      {/* Outro */}
      <Sequence from={cardFrames + sceneTotalFrames} durationInFrames={cardFrames}>
        <OutroCard theme={theme} />
      </Sequence>

      {/* Narration runs the whole video */}
      {audio && <Audio src={audio} />}

      {/* Background music, ducked */}
      {music && <Audio src={music} volume={theme.musicDuckVolume} loop />}

      {/* Word-level captions, anchored to the narration timeline. Narration
          starts cardSeconds in, so we offset the caption window by that much. */}
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
