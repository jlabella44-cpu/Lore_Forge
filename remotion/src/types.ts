import { z } from "zod";

export const toneSchema = z.enum(["dark", "hype", "cozy"]);
export type Tone = z.infer<typeof toneSchema>;

export const sectionSchema = z.enum([
  "hook",
  "world_tease",
  "emotional_pull",
  "social_proof",
  "cta",
]);
export type Section = z.infer<typeof sectionSchema>;

/**
 * One scene = one image + the section of the script it supports + how long
 * it holds on screen. Backend computes `durationSeconds` from per-section
 * narration word counts.
 */
export const sceneSchema = z.object({
  section: sectionSchema,
  image: z.string(),
  durationSeconds: z.number().min(0.3).max(60),
});
export type Scene = z.infer<typeof sceneSchema>;

/** One word of the narration with its start/end timestamps in seconds. */
export const captionWordSchema = z.object({
  word: z.string(),
  start: z.number().min(0),
  end: z.number().min(0),
});
export type CaptionWord = z.infer<typeof captionWordSchema>;

/**
 * Full props the backend renderer emits and the LoreForge composition consumes.
 *
 * `scenes` replaces the old flat `images` array — every scene is anchored to
 * a script section and carries its own duration. `captions` is the
 * word-level Whisper transcript, used by the CaptionsOverlay.
 */
export const packagePropsSchema = z.object({
  tone: toneSchema,
  title: z.string(),
  author: z.string(),
  cardSeconds: z.number().default(2),
  scenes: z.array(sceneSchema).min(1),
  audio: z.string().optional(),
  music: z.string().optional(),
  captions: z.array(captionWordSchema).default([]),
  /** Total video duration in seconds. intro + narration + outro. */
  durationSeconds: z.number().min(10).max(120),
});
export type PackageProps = z.infer<typeof packagePropsSchema>;

// ---------------------------------------------------------------------------
// LIST format — variable-length scenes keyed by book title, not section
// ---------------------------------------------------------------------------

export const listSceneSchema = z.object({
  label: z.string(),
  image: z.string(),
  durationSeconds: z.number().min(0.3).max(120),
});
export type ListScene = z.infer<typeof listSceneSchema>;

export const listPropsSchema = z.object({
  tone: toneSchema,
  title: z.string(),
  author: z.string(),
  cardSeconds: z.number().default(2),
  scenes: z.array(listSceneSchema).min(1),
  audio: z.string().optional(),
  music: z.string().optional(),
  captions: z.array(captionWordSchema).default([]),
  durationSeconds: z.number().min(10).max(600),
});
export type ListProps = z.infer<typeof listPropsSchema>;
