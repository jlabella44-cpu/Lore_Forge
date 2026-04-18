import { clsx } from "clsx";

export type ChipVariant =
  | "plain"
  | "ok"
  | "warn"
  | "info"
  | "accent"
  | "ember"
  | "err";

const VARIANT_STYLES: Record<ChipVariant, string> = {
  plain: "border-hair text-fg-2",
  ok: "text-[oklch(92%_0.1_155)] bg-ok-soft border-[oklch(78%_0.13_155/0.2)]",
  warn: "text-[oklch(92%_0.1_85)] bg-warn-soft border-[oklch(82%_0.15_85/0.2)]",
  info: "text-[oklch(90%_0.1_230)] bg-info-soft border-[oklch(75%_0.12_230/0.2)]",
  accent:
    "text-[oklch(90%_0.1_285)] bg-accent-soft border-[oklch(72%_0.14_285/0.25)]",
  ember:
    "text-[oklch(92%_0.12_65)] bg-ember-soft border-[oklch(78%_0.16_65/0.25)]",
  err: "text-[oklch(90%_0.12_25)] bg-err-soft border-[oklch(70%_0.19_25/0.25)]",
};

const DOT_STYLES: Record<ChipVariant, string> = {
  plain: "bg-fg-3",
  ok: "bg-ok",
  warn: "bg-warn",
  info: "bg-info",
  accent: "bg-accent",
  ember: "bg-ember",
  err: "bg-err",
};

export function Chip({
  variant = "plain",
  children,
  className,
  dot = true,
}: {
  variant?: ChipVariant;
  children: React.ReactNode;
  className?: string;
  dot?: boolean;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-[4px] border px-2 py-1 font-mono text-[10.5px] uppercase tracking-[0.08em]",
        VARIANT_STYLES[variant],
        className,
      )}
    >
      {dot && (
        <span className={clsx("h-[5px] w-[5px] rounded-full", DOT_STYLES[variant])} />
      )}
      {children}
    </span>
  );
}
