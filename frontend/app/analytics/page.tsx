"use client";

import { useEffect, useState } from "react";

import { apiFetch, dollars, type CostSummary } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { PageHead } from "@/components/ui/PageHead";

export default function AnalyticsPage() {
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
        eyebrow="Operations · Observability"
        title="Analytics"
        lede="Rolling 30-day view of generation cost across every pipeline call."
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
          {/* Stat tiles */}
          <div className="mb-7 grid grid-cols-4 gap-3.5">
            <Stat
              label="Packages · 30d"
              value={String(summary.per_package.length)}
            />
            <Stat
              label="Calls · 30d"
              value={String(summary.record_count)}
            />
            <Stat label="Spend · 30d" value={dollars(summary.total_cents)} />
            <Stat
              label="Avg cost / pkg"
              value={
                summary.per_package.length > 0
                  ? dollars(summary.total_cents / summary.per_package.length)
                  : "—"
              }
            />
          </div>

          {/* Cost by call */}
          <Card className="mb-7">
            <div className="mb-4 flex items-center justify-between">
              <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
                Cost by call · 30 days
              </div>
              <span className="font-mono text-[11px] text-fg-3">
                {summary.record_count} calls · {summary.total_usd}
              </span>
            </div>
            <CostByCall summary={summary} />
          </Card>

          <Card>
            <div className="mb-4 font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
              Most expensive packages
            </div>
            <div className="grid gap-1.5">
              {summary.per_package.slice(0, 10).map((p) => (
                <div
                  key={p.package_id}
                  className="flex items-center justify-between border-b border-hair py-2 text-sm last:border-0"
                >
                  <div>
                    <div className="text-fg-1">{p.book_title}</div>
                    <div className="mt-0.5 font-mono text-[11px] text-fg-4">
                      pkg #{p.package_id} · rev {p.revision_number}
                    </div>
                  </div>
                  <span className="font-mono text-fg-2 tabular-nums">
                    {dollars(p.cents)}
                  </span>
                </div>
              ))}
              {summary.per_package.length === 0 && (
                <div className="py-4 text-center text-sm text-fg-3">
                  No packages yet.
                </div>
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-hair bg-white/[0.015] p-5">
      <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
        {label}
      </div>
      <div className="mt-2 font-serif text-[28px] font-[450] leading-none tracking-[-0.02em] text-fg-0">
        {value}
      </div>
    </div>
  );
}

function CostByCall({ summary }: { summary: CostSummary }) {
  const rows = Object.entries(summary.by_call_name)
    .map(([name, info]) => ({ name, ...info }))
    .sort((a, b) => b.cents - a.cents);
  const max = Math.max(summary.total_cents, 1);
  return (
    <div className="grid gap-2">
      {rows.map((row) => {
        const pct = (row.cents / max) * 100;
        return (
          <div
            key={row.name}
            className="grid grid-cols-[200px_1fr_90px_60px] items-center gap-3.5"
          >
            <span className="truncate font-mono text-xs text-fg-1">
              {row.name}
            </span>
            <div className="h-1.5 overflow-hidden rounded-[3px] bg-white/[0.04]">
              <div
                className="h-full"
                style={{
                  width: `${pct}%`,
                  background:
                    "linear-gradient(90deg, var(--accent-dim), var(--accent))",
                }}
              />
            </div>
            <span className="text-right font-mono text-xs text-fg-2 tabular-nums">
              {dollars(row.cents)}
            </span>
            <span className="text-right font-mono text-[11px] text-fg-4 tabular-nums">
              {row.count}×
            </span>
          </div>
        );
      })}
      {rows.length === 0 && (
        <div className="py-4 text-center text-sm text-fg-3">
          No cost records in the last 30 days.
        </div>
      )}
    </div>
  );
}
