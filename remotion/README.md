# Lore Forge — Remotion

Video assembly for Phase 2. One composition (`LoreForge`) parameterized by tone
(`dark` / `hype` / `cozy`) renders a 9:16 short from an approved content
package.

## Layout

```
src/
  index.ts          entry — registers the Remotion root
  Root.tsx          <Composition> registration, calls calculateMetadata
  LoreForge.tsx     main composition: intro card → slideshow → outro card
  theme.ts          per-tone palette, typography, music duck volume
  types.ts          Zod schema for composition props (input contract)
  defaultProps.ts   SVG placeholder images so Studio runs with no assets
  scenes/
    IntroCard.tsx   animated title + author card, tone-colored
    Slideshow.tsx   crossfaded image sequence with subtle Ken Burns zoom
    OutroCard.tsx   "Link in bio" / per-tone CTA card
```

## Input contract

See [`src/types.ts`](./src/types.ts) — a Zod schema the backend must satisfy
when invoking a render. Key fields:

| Field             | Required | Notes                                                         |
| ----------------- | -------- | ------------------------------------------------------------- |
| `tone`            | ✓        | `dark` \| `hype` \| `cozy`                                    |
| `title`, `author` | ✓        | Shown on the intro card                                       |
| `images`          | ✓        | Array of URLs or absolute local paths. 4–5 ideal.             |
| `durationSeconds` | ✓        | Total video length. Pass the narration mp3 duration.          |
| `cardSeconds`     |          | Intro + outro hold duration. Defaults to `2`.                 |
| `audio`           |          | Narration mp3 URL/path. Omit for a silent preview.            |
| `music`           |          | Background music URL/path. Auto-ducked using `theme.ts`.      |

## Commands

```bash
# One-time install
npm install

# Live preview in the browser (default props use SVG placeholders)
npm run studio

# List compositions
npm run compositions -- src/index.ts

# Render an mp4 from the backend-assembled input JSON
npx remotion render src/index.ts LoreForge out.mp4 \
  --props='{"tone":"dark","title":"...","author":"...","images":[...],"durationSeconds":90,"audio":"file:///path/to/narration.mp3"}'

# Or pass props via file
npx remotion render src/index.ts LoreForge out.mp4 --props=./props.json
```

The backend ticket (next up) wires `POST /packages/{id}/render` to shell out
with paths resolved from the approved package + the backend's assets dir.

## Asset conventions

- Images: 9:16, at least 1080×1920. `objectFit: cover` will crop anything else.
- Narration: mp3, mono or stereo, 44.1kHz. Duration drives `durationSeconds`.
- Music: in `../backend/assets/music/{dark,hype,cozy}/` (curated from
  YouTube Audio Library + Pixabay). Remotion picks one per render.

Nothing binary is committed to this repo — renders use paths provided at
invocation time.
