"use client";

import { useEffect, useState } from "react";

import { apiFetch, dollars, type CostSummary } from "@/lib/api";
import { Card, HeroCard } from "@/components/ui/Card";
import { PageHead } from "@/components/ui/PageHead";

const PROVIDER_LABEL: Record<string, string> = {
  claude: "Claude",
  openai: "OpenAI",
  qwen: "Qwen",
  wanx: "Wanx",
  dalle: "DALL·E",
  imagen: "Imagen",
  replicate: "Replicate",
};

export default function SettingsPage() {
  const [summary, setSummary] = useState<CostSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<CostSummary>("/analytics/cost?days=30")
      .then(setSummary)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="mx-auto max-w-[1240px] px-10 pb-20 pt-9">
      <PageHead
        eyebrow="Operations"
        title="Costs & Limits"
        lede="Budget guardrail, provider breakdown, and per-package spend. Configure keys in .env."
      />

      {error && (
        <div className="mb-6 rounded-lg border border-err/30 bg-err-soft p-4 text-sm text-[oklch(90%_0.12_25)]">
          {error}
        </div>
      )}

      {!summary ? (
        <Card className="text-sm text-fg-3">Loading…</Card>
      ) : (
        <>
          <BudgetHero budget={summary.budget} />

          <div className="mt-7 grid grid-cols-1 gap-5 md:grid-cols-2">
            <ByProviderCard summary={summary} />
            <TopPackagesCard summary={summary} />
          </div>
        </>
      )}
    </div>
  );
}

function BudgetHero({ budget }: { budget: CostSummary["budget"] }) {
  const { today_cents, daily_cents, remaining_cents } = budget;
  const cap = daily_cents ?? 0;
  const pct = cap > 0 ? Math.max(0, Math.min(100, (today_cents / cap) * 100)) : 0;
  return (
    <HeroCard>
      <div className="mb-4 flex items-baseline justify-between">
        <div>
          <span className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
            Rolling 24h budget
          </span>
          <div className="mt-2.5 flex items-baseline gap-2.5">
            <span className="font-serif text-[48px] font-[450] leading-none tracking-[-0.02em] text-fg-0">
              {dollars(today_cents)}
            </span>
            <span className="text-sm text-fg-3">
              {cap > 0 ? `of $${(cap / 100).toFixed(2)} daily cap` : "no cap configured"}
            </span>
          </div>
        </div>
        {cap > 0 && (
          <div className="text-right">
            <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
              Remaining
            </div>
            <div className="mt-1 font-serif text-[28px] font-[450] tracking-[-0.01em] text-fg-0">
              {dollars(Math.max(0, remaining_cents ?? 0))}
            </div>
          </div>
        )}
      </div>
      <div className="h-1.5 overflow-hidden rounded-[3px] bg-white/[0.06]">
        <div
          className="h-full"
          style={{
            width: `${pct}%`,
            background: "linear-gradient(90deg, var(--accent), var(--ember))",
          }}
        />
      </div>
      <div className="mt-2 flex justify-between font-mono text-[11px] tracking-[0.08em] text-fg-3">
        <span>$0</span>
        <span>{pct.toFixed(0)}% used</span>
        <span>{cap > 0 ? `$${(cap / 100).toFixed(0)}` : "—"}</span>
      </div>
    </HeroCard>
  );
}

function ByProviderCard({ summary }: { summary: CostSummary }) {
  const entries = Object.entries(summary.by_provider).sort(
    (a, b) => b[1] - a[1],
  );
  const total = Math.max(summary.total_cents, 1);
  return (
    <Card>
      <div className="mb-4 font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
        By Provider · 30 days
      </div>
      <div className="grid gap-3">
        {entries.map(([provider, cents]) => {
          const pct = (cents / total) * 100;
          return (
            <div key={provider}>
              <div className="mb-1 flex justify-between text-[13px]">
                <span className="text-fg-1">
                  {PROVIDER_LABEL[provider] ?? provider}
                </span>
                <span className="font-mono text-fg-2 tabular-nums">
                  {dollars(cents)}
                </span>
              </div>
              <div className="h-1 overflow-hidden rounded-[3px] bg-white/[0.04]">
                <div
                  className="h-full"
                  style={{ width: `${pct}%`, background: "var(--accent)" }}
                />
              </div>
            </div>
          );
        })}
        {entries.length === 0 && (
          <div className="py-4 text-center text-sm text-fg-3">
            No spend recorded in the last 30 days.
          </div>
        )}
      </div>
    </Card>
  );
}

function TopPackagesCard({ summary }: { summary: CostSummary }) {
  const rows = summary.per_package.slice(0, 8);
  return (
    <Card>
      <div className="mb-4 font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
        Top packages
      </div>
      <div className="grid gap-0">
        {rows.map((p) => (
          <div
            key={p.package_id}
            className="flex items-center justify-between border-b border-hair py-2 text-[13px] last:border-0"
          >
            <div className="min-w-0">
              <div className="truncate text-fg-1">{p.book_title}</div>
              <div className="mt-0.5 font-mono text-[11px] text-fg-4">
                pkg #{p.package_id} · rev {p.revision_number}
              </div>
            </div>
            <span className="font-mono text-fg-2 tabular-nums">
              {dollars(p.cents)}
            </span>
          </div>
        ))}
        {rows.length === 0 && (
          <div className="py-4 text-center text-sm text-fg-3">
            No packages yet.
          </div>
        )}
      </div>
    </Card>
  );
}
