import { clsx } from "clsx";

export function Card({
  className,
  children,
  ...rest
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...rest}
      className={clsx(
        "rounded-lg border border-hair bg-white/[0.015] p-[20px_22px]",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Hero card with the accent (top-right) + ember (bottom-left) radial glows. */
export function HeroCard({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={clsx(
        "relative overflow-hidden rounded-lg border border-hair-strong p-[28px_30px]",
        className,
      )}
      style={{
        background:
          "linear-gradient(180deg, oklch(18% 0.02 260), oklch(15% 0.015 260))",
      }}
    >
      {/* Accent top-right */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full"
        style={{
          background:
            "radial-gradient(circle, oklch(72% 0.14 285 / 0.18), transparent 60%)",
        }}
      />
      {/* Ember bottom-left */}
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-20 -left-20 h-64 w-64 rounded-full opacity-50"
        style={{
          background:
            "radial-gradient(circle, oklch(78% 0.16 65 / 0.14), transparent 60%)",
        }}
      />
      <div className="relative">{children}</div>
    </div>
  );
}
