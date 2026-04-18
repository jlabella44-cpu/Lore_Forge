export function ScoreBar({
  score,
  width = 56,
}: {
  score: number;
  width?: number;
}) {
  const pct = Math.max(0, Math.min(100, score));
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono text-xs tabular-nums text-fg-1">
        {score.toFixed(1)}
      </span>
      <div
        className="overflow-hidden rounded-[2px] bg-white/[0.06]"
        style={{ width, height: 3 }}
      >
        <div
          className="h-full rounded-[2px]"
          style={{
            width: `${pct}%`,
            background: "linear-gradient(90deg, var(--accent-dim), var(--accent))",
          }}
        />
      </div>
    </div>
  );
}
