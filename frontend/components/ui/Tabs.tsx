export type TabDef<K extends string = string> = {
  key: K;
  label: string;
  count?: number;
};

export function Tabs<K extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: TabDef<K>[];
  active: K;
  onChange: (k: K) => void;
}) {
  return (
    <div className="mb-6 flex gap-1 border-b border-hair">
      {tabs.map((t) => {
        const on = t.key === active;
        return (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            className={`-mb-px flex items-center gap-2 border-b-2 px-3.5 py-2.5 text-[13px] transition-colors ${
              on
                ? "border-accent text-fg-0"
                : "border-transparent text-fg-3 hover:text-fg-1"
            }`}
          >
            {t.label}
            {typeof t.count === "number" && (
              <span className="rounded-[3px] bg-white/[0.05] px-1.5 py-[1px] font-mono text-[10px] text-fg-3">
                {t.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
