"use client";

import { useEffect, useState } from "react";

import { apiFetch, CostSummary, dollars } from "@/lib/api";

const PROVIDER_LABEL: Record<string, string> = {
  claude: "Claude",
  openai: "OpenAI",
  qwen: "Qwen",
  wanx: "Wanx",
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
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-3xl font-semibold">Settings</h1>
      <p className="mt-2 text-sm opacity-70">
        API keys, publish schedule, and source toggles live in{" "}
        <code>.env</code>. Cost telemetry below is the only real UI
        content here right now.
      </p>

      <section className="mt-8 rounded-lg border border-white/10 p-6">
        <header className="mb-4 flex items-baseline justify-between">
          <h2 className="font-medium">Last 30 days</h2>
          {summary && (
            <span className="text-xs opacity-60">
              {summary.record_count} calls
            </span>
          )}
        </header>

        {error && (
          <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
            {error}
          </div>
        )}

        {!summary && !error && (
          <div className="text-sm opacity-60">Loading…</div>
        )}

        {summary && (
          <>
            <div className="mb-6 flex items-baseline gap-3">
              <span className="text-4xl font-semibold">
                {summary.total_usd === "0.00"
                  ? "$0.00"
                  : `$${summary.total_usd}`}
              </span>
              <span className="text-sm opacity-70">
                · {summary.per_package.length} package
                {summary.per_package.length === 1 ? "" : "s"}
              </span>
            </div>

            <BudgetCard budget={summary.budget} />
            <ProviderBreakdown byProvider={summary.by_provider} />
            <CallBreakdown byCallName={summary.by_call_name} />
            <PackageBreakdown packages={summary.per_package} />
          </>
        )}
      </section>
    </main>
  );
}

function BudgetCard({
  budget,
}: {
  budget: CostSummary["budget"];
}) {
  if (budget.daily_cents == null) {
    return (
      <div className="mb-6 rounded-md border border-white/5 bg-white/5 p-3 text-xs opacity-70">
        Daily cost guardrail is off (COST_DAILY_BUDGET_CENTS ≤ 0).{" "}
        Set it in <code>.env</code> to enforce a cap.
      </div>
    );
  }

  const pct = Math.min(
    100,
    Math.round((budget.today_cents / budget.daily_cents) * 100),
  );
  const barColor =
    pct >= 100
      ? "bg-red-500/70"
      : pct >= 80
        ? "bg-amber-500/70"
        : "bg-green-500/70";

  return (
    <div className="mb-6 rounded-md border border-white/5 bg-white/5 p-4 text-sm">
      <div className="mb-2 flex items-baseline justify-between">
        <span className="text-xs opacity-60 uppercase tracking-wider">
          Today (rolling 24h)
        </span>
        <span className="tabular-nums opacity-80">
          {dollars(budget.today_cents)} / {dollars(budget.daily_cents)}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
        <div
          className={`h-full ${barColor} transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {pct >= 100 && (
        <p className="mt-2 text-xs text-red-200">
          Budget exceeded — generate and render calls return 429 until the
          rolling window clears.
        </p>
      )}
    </div>
  );
}

function ProviderBreakdown({
  byProvider,
}: {
  byProvider: Record<string, number>;
}) {
  const entries = Object.entries(byProvider).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) return null;
  return (
    <div className="mb-6">
      <h3 className="mb-2 text-xs font-medium opacity-60 uppercase tracking-wider">
        By provider
      </h3>
      <ul className="space-y-1">
        {entries.map(([provider, cents]) => (
          <li key={provider} className="flex items-center justify-between text-sm">
            <span>{PROVIDER_LABEL[provider] ?? provider}</span>
            <span className="tabular-nums opacity-80">{dollars(cents)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CallBreakdown({
  byCallName,
}: {
  byCallName: Record<string, { count: number; cents: number }>;
}) {
  const entries = Object.entries(byCallName).sort(
    (a, b) => b[1].cents - a[1].cents,
  );
  if (entries.length === 0) return null;
  return (
    <details className="mb-6">
      <summary className="mb-2 cursor-pointer text-xs font-medium opacity-60 uppercase tracking-wider">
        By call ({entries.length})
      </summary>
      <ul className="space-y-1">
        {entries.map(([name, { count, cents }]) => (
          <li key={name} className="flex items-center justify-between text-sm">
            <span className="font-mono text-xs">{name}</span>
            <span className="tabular-nums opacity-80">
              {count}× · {dollars(cents)}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function PackageBreakdown({
  packages,
}: {
  packages: CostSummary["per_package"];
}) {
  if (packages.length === 0) return null;
  return (
    <details>
      <summary className="mb-2 cursor-pointer text-xs font-medium opacity-60 uppercase tracking-wider">
        By package ({packages.length})
      </summary>
      <ul className="space-y-1">
        {packages.map((p) => (
          <li
            key={p.package_id}
            className="flex items-center justify-between gap-3 text-sm"
          >
            <a
              className="truncate underline-offset-4 hover:underline"
              href={`/book/${p.book_id}`}
            >
              {p.book_title}{" "}
              <span className="opacity-60">· rev {p.revision_number}</span>
            </a>
            <span className="tabular-nums opacity-80">{dollars(p.cents)}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
