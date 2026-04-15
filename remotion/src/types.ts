import { z } from "zod";

export const toneSchema = z.enum(["dark", "hype", "cozy"]);
export type Tone = z.infer<typeof toneSchema>;

/**
 * Props the Remotion composition accepts.
 *
 * Paths can be absolute local paths (from a backend render invocation) or URLs
 * (handy when previewing in Studio from a web host).
 */
export const packagePropsSchema = z.object({
  tone: toneSchema,
  title: z.string(),
  author: z.string(),
  /** How long to hold the intro + outro cards, in seconds. */
  cardSeconds: z.number().default(2),
  /** Image URLs/paths, rendered as a crossfaded slideshow. 4-5 per video. */
  images: z.array(z.string()).min(1),
  /** Optional narration mp3 URL/path. Omit for silent Studio preview. */
  audio: z.string().optional(),
  /** Optional background music URL/path. Auto-ducked under narration. */
  music: z.string().optional(),
  /** Total video duration in seconds. Pass the narration mp3 duration. */
  durationSeconds: z.number().min(10).max(120),
});

export type PackageProps = z.infer<typeof packagePropsSchema>;
