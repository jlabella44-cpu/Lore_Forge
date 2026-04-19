import { clsx } from "clsx";

/**
 * Deterministic procedural cover used when a ContentItem has no real
 * `cover_url`. 8 palettes × 4 motifs, keyed by a numeric seed so the
 * same item always renders the same cover. Renamed from BookCover in
 * B7 — the rendered output is identical (the design works just as well
 * for film posters and recipe thumbnails as for book covers).
 */

const PALETTES: Array<{ bg: string; accent: string; ink: string }> = [
  { bg: "oklch(32% 0.05 265)", accent: "oklch(78% 0.13 65)", ink: "oklch(90% 0.03 65)" },
  { bg: "oklch(28% 0.08 300)", accent: "oklch(82% 0.12 180)", ink: "oklch(92% 0.04 180)" },
  { bg: "oklch(30% 0.06 20)", accent: "oklch(80% 0.14 40)", ink: "oklch(90% 0.05 40)" },
  { bg: "oklch(26% 0.04 160)", accent: "oklch(78% 0.14 120)", ink: "oklch(92% 0.05 120)" },
  { bg: "oklch(32% 0.07 260)", accent: "oklch(80% 0.15 285)", ink: "oklch(94% 0.06 285)" },
  { bg: "oklch(26% 0.03 90)", accent: "oklch(82% 0.14 85)", ink: "oklch(94% 0.05 85)" },
  { bg: "oklch(24% 0.02 260)", accent: "oklch(78% 0.1 230)", ink: "oklch(92% 0.04 230)" },
  { bg: "oklch(30% 0.04 30)", accent: "oklch(82% 0.15 20)", ink: "oklch(94% 0.05 20)" },
];

type Motif = "moon" | "obelisk" | "constellation" | "bars";
const MOTIFS: Motif[] = ["moon", "obelisk", "constellation", "bars"];

/** Cheap deterministic hash — good enough for 8-way palette selection. */
function seedFrom(input: string): number {
  let h = 2166136261;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function ContentCover({
  coverUrl,
  title,
  subtitle,
  className,
}: {
  coverUrl?: string | null;
  title: string;
  subtitle: string;
  className?: string;
}) {
  if (coverUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={coverUrl}
        alt={`Cover of ${title}`}
        className={clsx(
          "block aspect-[2/3] h-full w-full rounded-md object-cover",
          className,
        )}
      />
    );
  }

  const seed = seedFrom(`${title}|${subtitle}`);
  const palette = PALETTES[seed % PALETTES.length];
  const motif = MOTIFS[(seed >> 3) % MOTIFS.length];

  return (
    <svg
      viewBox="0 0 200 300"
      preserveAspectRatio="xMidYMid slice"
      className={clsx(
        "block aspect-[2/3] h-full w-full overflow-hidden rounded-md",
        className,
      )}
      aria-label={`Procedural cover for ${title}`}
    >
      <rect width={200} height={300} fill={palette.bg} />
      {/* Soft gradient wash */}
      <defs>
        <linearGradient id={`wash-${seed}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="white" stopOpacity="0.08" />
          <stop offset="1" stopColor="black" stopOpacity="0.2" />
        </linearGradient>
      </defs>
      <rect width={200} height={300} fill={`url(#wash-${seed})`} />

      {motif === "moon" && (
        <circle cx={130} cy={90} r={38} fill={palette.accent} opacity={0.8} />
      )}
      {motif === "obelisk" && (
        <>
          <rect x={88} y={70} width={24} height={140} fill={palette.accent} opacity={0.85} />
          <polygon points="88,70 100,50 112,70" fill={palette.accent} />
        </>
      )}
      {motif === "constellation" && (
        <>
          {Array.from({ length: 8 }).map((_, i) => {
            const x = 40 + ((seed >> i) % 120);
            const y = 70 + ((seed >> (i + 3)) % 140);
            return <circle key={i} cx={x} cy={y} r={2.5} fill={palette.accent} />;
          })}
        </>
      )}
      {motif === "bars" && (
        <>
          <rect x={30} y={140} width={140} height={2} fill={palette.accent} />
          <rect x={30} y={152} width={80} height={2} fill={palette.accent} opacity={0.7} />
          <rect x={30} y={164} width={110} height={2} fill={palette.accent} opacity={0.5} />
        </>
      )}

      {/* Title + subtitle, tight */}
      <text
        x={20}
        y={240}
        fontFamily="Georgia, serif"
        fontSize={14}
        fontWeight={500}
        fill={palette.ink}
      >
        {title.length > 24 ? title.slice(0, 22) + "…" : title}
      </text>
      <text
        x={20}
        y={262}
        fontFamily="Georgia, serif"
        fontSize={10}
        fill={palette.ink}
        opacity={0.7}
      >
        {subtitle.length > 28 ? subtitle.slice(0, 26) + "…" : subtitle}
      </text>
    </svg>
  );
}
