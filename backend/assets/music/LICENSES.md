# Music licensing notes

One folder per tone: `dark/`, `hype/`, `cozy/`. The renderer picks a random
track from the tone folder at render time; empty folders mean "no music".

## Curation policy

Only add tracks that are:

- **Royalty-free** with clear attribution terms, **or**
- **Creative Commons** (CC0, CC BY, CC BY-SA), **or**
- Licensed via a platform that permits TikTok / YouTube Shorts / Instagram
  Reels / Threads re-uploads (YouTube Audio Library is the usual source).

## Recommended sources (free)

1. **YouTube Audio Library** — `https://studio.youtube.com/…/music`
   Free for YouTube creators. Most tracks allow re-upload to TikTok / IG /
   Threads. Filter by mood (Dramatic → dark, Inspirational → hype, Calm → cozy).
2. **Pixabay Music** — `https://pixabay.com/music/` — fully royalty-free,
   no attribution required. Good cozy + cinematic catalog.
3. **Freesound** (CC0 filter only) — `https://freesound.org/` — good for
   short stings or texture loops.

## Recording

When adding a track, append a line to this file with:

    <tone>/<filename>    —    <source>    —    <license>    —    <track URL>

Example:

    dark/cinematic_dusk.mp3    —    Pixabay    —    Royalty-free    —    https://pixabay.com/music/cinematic-dusk-12345/

A curation pass of 5-8 tracks per tone is enough — the renderer shuffles
across them so repeated uses of the same tone don't sound identical.

## Format

- **Preferred**: mp3, 44.1 kHz, stereo. m4a, wav, ogg also supported.
- **Duration**: 60-120 seconds is ideal; longer tracks are fine (looped in
  Remotion, ducked under narration via the tone's `musicDuckVolume`).
