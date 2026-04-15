import { AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * Evenly distributes `images` across `durationInFrames` with a short crossfade
 * at each boundary. Each image holds full-frame (object-fit: cover).
 */
export function Slideshow({
  images,
  durationInFrames,
}: {
  images: string[];
  durationInFrames: number;
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (images.length === 0) return null;

  const perImageFrames = durationInFrames / images.length;
  // Crossfade overlaps the last ~0.4s of each image with the first of the next.
  const fadeFrames = Math.min(Math.round(fps * 0.4), Math.floor(perImageFrames / 2));

  return (
    <AbsoluteFill>
      {images.map((src, index) => {
        const start = index * perImageFrames;
        const end = start + perImageFrames;
        const fadeInEnd = start + fadeFrames;
        const fadeOutStart = end - fadeFrames;

        let opacity = 0;
        if (frame >= start - fadeFrames && frame <= end) {
          if (frame < fadeInEnd) {
            opacity = interpolate(frame, [start - fadeFrames, fadeInEnd], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
          } else if (frame > fadeOutStart && index < images.length - 1) {
            opacity = interpolate(frame, [fadeOutStart, end], [1, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
          } else {
            opacity = 1;
          }
        }

        if (opacity <= 0) return null;

        // Subtle Ken Burns: slow zoom over the image's on-screen window.
        const zoom = interpolate(frame, [start, end], [1.0, 1.08], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

        return (
          <AbsoluteFill key={src + index} style={{ opacity }}>
            <Img
              src={src}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                transform: `scale(${zoom})`,
              }}
            />
          </AbsoluteFill>
        );
      })}
    </AbsoluteFill>
  );
}
