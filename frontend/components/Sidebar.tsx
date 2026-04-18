"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { BookOpen, Layers, BarChart3, Coins, Flame } from "lucide-react";
import { apiFetch, type CostSummary } from "@/lib/api";

type CountKey = "books" | "series";

type NavItem = {
  href: string;
  label: string;
  icon: typeof BookOpen;
  countKey?: CountKey;
};

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "Pipeline",
    items: [
      { href: "/dashboard", label: "Books", icon: BookOpen, countKey: "books" },
      { href: "/series", label: "Series", icon: Layers, countKey: "series" },
    ],
  },
  {
    section: "Operations",
    items: [
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/settings", label: "Costs", icon: Coins },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const [counts, setCounts] = useState<Partial<Record<CountKey, number>>>({});
  const [budget, setBudget] = useState<CostSummary["budget"] | null>(null);

  useEffect(() => {
    apiFetch<Array<{ id: number }>>("/books")
      .then((b) => setCounts((c) => ({ ...c, books: b.length })))
      .catch(() => {});
    apiFetch<Array<{ id: number }>>("/series")
      .then((s) => setCounts((c) => ({ ...c, series: s.length })))
      .catch(() => {});
    apiFetch<CostSummary>("/analytics/cost?days=1")
      .then((cost) => setBudget(cost.budget))
      .catch(() => {});
  }, []);

  return (
    <aside
      className="sticky top-0 z-[2] flex h-screen flex-col border-r border-hair"
      style={{
        background:
          "linear-gradient(180deg, oklch(14% 0.014 260), oklch(13% 0.012 260))",
      }}
    >
      {/* Brand */}
      <div className="flex items-center gap-3 border-b border-hair px-5 pb-5 pt-[22px]">
        <Sigil />
        <div>
          <div className="font-serif text-[17px] font-medium tracking-[0.01em] text-fg-0">
            Lore Forge
          </div>
          <div className="mt-0.5 font-mono text-[9.5px] uppercase tracking-[0.18em] text-fg-3">
            Content · Engine
          </div>
        </div>
      </div>

      {/* Nav sections */}
      <div className="flex-1 overflow-y-auto">
        {NAV.map(({ section, items }) => (
          <div key={section} className="px-3 pb-1.5 pt-[18px]">
            <div className="px-2.5 pb-2 font-mono text-[10px] uppercase tracking-[0.16em] text-fg-4">
              {section}
            </div>
            {items.map(({ href, label, icon: Icon, countKey }) => {
              const active =
                pathname === href || pathname.startsWith(href + "/");
              const count = countKey ? counts[countKey] : undefined;
              return (
                <Link
                  key={href}
                  href={href}
                  className={`group relative flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-[13.5px] transition-colors ${
                    active
                      ? "bg-white/[0.05] text-fg-0"
                      : "text-fg-2 hover:bg-white/[0.03] hover:text-fg-1"
                  }`}
                >
                  {active && (
                    <span
                      aria-hidden
                      className="absolute bottom-2.5 top-2.5 w-0.5 rounded-[2px]"
                      style={{
                        left: "-12px",
                        background: "var(--accent)",
                        boxShadow: "0 0 8px var(--accent)",
                      }}
                    />
                  )}
                  <Icon
                    className={`h-4 w-4 flex-shrink-0 ${
                      active ? "opacity-100" : "opacity-70"
                    }`}
                    style={active ? { color: "var(--accent)" } : undefined}
                  />
                  <span className="flex-1">{label}</span>
                  {typeof count === "number" && (
                    <span className="rounded-[3px] bg-white/[0.05] px-1.5 py-0.5 font-mono text-[10.5px] text-fg-3">
                      {count}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </div>

      {/* Budget footer */}
      <div className="mt-auto border-t border-hair px-4 py-3.5 text-[11.5px] text-fg-3">
        {budget ? <BudgetMini budget={budget} /> : <BudgetSkeleton />}
      </div>
    </aside>
  );
}

function Sigil() {
  return (
    <div
      className="relative grid h-7 w-7 place-items-center rounded-md"
      style={{
        background:
          "radial-gradient(circle at 30% 30%, oklch(85% 0.14 285 / 0.9), transparent 60%), linear-gradient(135deg, oklch(45% 0.14 285), oklch(30% 0.06 250))",
        boxShadow:
          "inset 0 0 0 1px oklch(100% 0 0 / 0.12), 0 0 20px oklch(72% 0.14 285 / 0.2)",
      }}
    >
      <Flame className="h-4 w-4" style={{ color: "oklch(98% 0.02 285)" }} />
    </div>
  );
}

function BudgetMini({ budget }: { budget: CostSummary["budget"] }) {
  const { today_cents, daily_cents } = budget;
  const cap = daily_cents ?? 0;
  const pct = cap > 0 ? Math.max(0, Math.min(100, (today_cents / cap) * 100)) : 0;
  return (
    <>
      <div className="mb-1.5 flex justify-between font-mono text-[10px] uppercase tracking-[0.1em]">
        <span>Today</span>
        <span>
          ${(today_cents / 100).toFixed(2)}
          {cap > 0 ? ` / $${(cap / 100).toFixed(0)}` : " · no cap"}
        </span>
      </div>
      <div className="h-[3px] overflow-hidden rounded-[2px] bg-white/[0.06]">
        <div
          className="h-full"
          style={{
            width: `${pct}%`,
            background: "linear-gradient(90deg, var(--accent), var(--ember))",
          }}
        />
      </div>
    </>
  );
}

function BudgetSkeleton() {
  return (
    <div className="font-mono text-[10px] uppercase tracking-[0.1em] opacity-60">
      Today —
    </div>
  );
}
