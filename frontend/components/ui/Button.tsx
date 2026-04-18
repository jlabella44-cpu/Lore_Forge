import { clsx } from "clsx";

export type ButtonVariant = "default" | "primary" | "ember" | "ok" | "ghost";
type ButtonSize = "md" | "sm";

const BASE =
  "inline-flex items-center gap-2 whitespace-nowrap rounded-md font-medium transition-[background,border-color,color,filter] duration-[120ms] disabled:cursor-not-allowed disabled:opacity-40";

const SIZES: Record<ButtonSize, string> = {
  md: "px-3.5 py-2 text-[13px]",
  sm: "px-2.5 py-[5px] text-xs",
};

const VARIANTS: Record<ButtonVariant, string> = {
  default:
    "border border-hair bg-white/[0.03] text-fg-1 hover:border-hair-strong hover:bg-white/[0.07]",
  primary:
    "border text-[oklch(15%_0.04_285)] font-semibold hover:brightness-110",
  ember:
    "border text-[oklch(18%_0.03_50)] font-semibold hover:brightness-110",
  ok: "border border-[oklch(78%_0.13_155/0.25)] bg-ok-soft text-[oklch(92%_0.1_155)] hover:bg-[oklch(78%_0.13_155/0.22)]",
  ghost:
    "border border-transparent bg-transparent text-fg-2 hover:bg-white/[0.04] hover:text-fg-1",
};

const PRIMARY_STYLE: React.CSSProperties = {
  background:
    "linear-gradient(180deg, oklch(72% 0.14 285), oklch(58% 0.16 285))",
  borderColor: "oklch(80% 0.12 285 / 0.4)",
  boxShadow:
    "0 0 0 1px oklch(100% 0 0 / 0.1) inset, 0 4px 20px oklch(72% 0.14 285 / 0.3)",
};

const EMBER_STYLE: React.CSSProperties = {
  background: "linear-gradient(180deg, oklch(82% 0.16 65), oklch(68% 0.16 50))",
  borderColor: "oklch(82% 0.16 65 / 0.4)",
  boxShadow:
    "0 0 0 1px oklch(100% 0 0 / 0.1) inset, 0 4px 20px oklch(78% 0.16 65 / 0.3)",
};

export const Button = ({
  variant = "default",
  size = "md",
  className,
  style,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
}) => {
  const combinedStyle =
    variant === "primary"
      ? { ...PRIMARY_STYLE, ...style }
      : variant === "ember"
        ? { ...EMBER_STYLE, ...style }
        : style;
  return (
    <button
      {...rest}
      style={combinedStyle}
      className={clsx(BASE, SIZES[size], VARIANTS[variant], className)}
    />
  );
};
