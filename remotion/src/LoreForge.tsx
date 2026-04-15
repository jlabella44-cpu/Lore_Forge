import { AbsoluteFill, Audio, Sequence, useVideoConfig } from "remotion";

import { IntroCard } from "./scenes/IntroCard";
import { OutroCard } from "./scenes/OutroCard";
import { Slideshow } from "./scenes/Slideshow";
import { THEMES } from "./theme";
import type { PackageProps } from "./types";

export const LoreForge: React.FC<PackageProps> = ({
  tone,
  title,
  author,
  cardSeconds,
  images,
  audio,
  music,
  durationSeconds,
}) => {
  const { fps } = useVideoConfig();
  const theme = THEMES[tone];

  const cardFrames = Math.round(cardSeconds * fps);
  const totalFrames = Math.round(durationSeconds * fps);
  const slideshowFrames = Math.max(
    totalFrames - cardFrames * 2,
    Math.round(fps * 3),
  );

  return (
    <AbsoluteFill style={{ backgroundColor: theme.background }}>
      {/* Intro */}
      <Sequence durationInFrames={cardFrames}>
        <IntroCard title={title} author={author} theme={theme} />
      </Sequence>

      {/* Slideshow */}
      <Sequence from={cardFrames} durationInFrames={slideshowFrames}>
        <Slideshow images={images} durationInFrames={slideshowFrames} />
      </Sequence>

      {/* Outro */}
      <Sequence from={cardFrames + slideshowFrames} durationInFrames={cardFrames}>
        <OutroCard theme={theme} />
      </Sequence>

      {/* Narration runs the whole video at full volume. */}
      {audio && <Audio src={audio} />}

      {/* Background music, ducked. */}
      {music && <Audio src={music} volume={theme.musicDuckVolume} loop />}
    </AbsoluteFill>
  );
};
