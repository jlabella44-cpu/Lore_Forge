export function PageHead({
  eyebrow,
  title,
  lede,
  actions,
}: {
  eyebrow?: string;
  title: string;
  lede?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-7 flex items-end justify-between gap-6 border-b border-hair pb-7">
      <div>
        {eyebrow && (
          <span className="mb-2.5 block font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
            {eyebrow}
          </span>
        )}
        <h1 className="max-w-[720px] font-serif text-[34px] font-[450] leading-[1.1] tracking-[-0.02em] text-fg-0">
          {title}
        </h1>
        {lede && (
          <p className="mt-2.5 max-w-[560px] text-sm leading-[1.55] text-fg-2">
            {lede}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-2.5">{actions}</div>
      )}
    </div>
  );
}
