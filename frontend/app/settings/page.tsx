"use client";

import { useEffect, useState } from "react";

import { apiFetch, dollars, type CostSummary } from "@/lib/api";
import { Button } from "@/components/ui/Button";
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

// ---------------------------------------------------------------------------
// /settings response shape — matches backend/app/routers/settings.py.
// ---------------------------------------------------------------------------

type SecretRow = {
  name: string;
  configured: boolean;
  last_four: string | null;
};

type SettingsSnapshot = {
  secret_keys: SecretRow[];
  providers: {
    script: string;
    meta: string;
    tts: string;
    image: string;
    renderer: string;
  };
  paths: {
    renders_dir: string;
    music_dir: string;
    database_url: string;
  };
  desktop_mode: boolean;
};

const PROVIDER_OPTIONS: Record<keyof SettingsSnapshot["providers"], string[]> = {
  script: ["claude", "openai", "qwen"],
  meta: ["claude", "openai", "qwen"],
  tts: ["openai", "kokoro", "dashscope", "elevenlabs"],
  image: ["wanx", "dalle", "imagen", "replicate", "sdxl_local", "midjourney_manual"],
  renderer: ["remotion", "ffmpeg"],
};

// Display name in the secrets table — falls back to the raw key
// (snake_case) so adding a new SECRET_KEY in secrets.py never strands
// a row with a missing label.
const SECRET_LABEL: Record<string, string> = {
  anthropic_api_key: "Anthropic API key",
  openai_api_key: "OpenAI API key",
  dashscope_api_key: "Dashscope (Qwen + Wanx) API key",
  elevenlabs_api_key: "ElevenLabs API key",
  nyt_api_key: "NYT Books API key",
  firecrawl_api_key: "Firecrawl API key",
  isbndb_api_key: "ISBNdb API key",
  youtube_client_id: "YouTube OAuth client ID",
  youtube_client_secret: "YouTube OAuth client secret",
  tiktok_client_key: "TikTok client key",
  tiktok_client_secret: "TikTok client secret",
  meta_app_id: "Meta (IG / Threads) app ID",
  meta_app_secret: "Meta (IG / Threads) app secret",
  amazon_associate_tag: "Amazon Associates tag",
  bookshop_affiliate_id: "Bookshop affiliate ID",
};

export default function SettingsPage() {
  const [summary, setSummary] = useState<CostSummary | null>(null);
  const [snapshot, setSnapshot] = useState<SettingsSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshSnapshot = () =>
    apiFetch<SettingsSnapshot>("/settings")
      .then(setSnapshot)
      .catch((e) => setError(String(e)));

  useEffect(() => {
    apiFetch<CostSummary>("/analytics/cost?days=30")
      .then(setSummary)
      .catch((e) => setError(String(e)));
    refreshSnapshot();
  }, []);

  return (
    <div className="mx-auto max-w-[1240px] px-10 pb-20 pt-9">
      <PageHead
        eyebrow="Operations"
        title="Settings & Costs"
        lede="Provider keys, routing, and the rolling 24h spend guardrail."
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

      {snapshot && (
        <>
          <div className="mt-9">
            <SecretsCard snapshot={snapshot} onChange={refreshSnapshot} />
          </div>
          <div className="mt-5">
            <ProvidersCard snapshot={snapshot} onChange={refreshSnapshot} />
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Provider keys
// ---------------------------------------------------------------------------

function SecretsCard({
  snapshot,
  onChange,
}: {
  snapshot: SettingsSnapshot;
  onChange: () => Promise<void>;
}) {
  const [editingKey, setEditingKey] = useState<string | null>(null);

  const closeAndRefresh = async () => {
    setEditingKey(null);
    await onChange();
  };

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
          Provider keys
        </div>
        <span className="font-mono text-[10.5px] text-fg-4">
          {snapshot.desktop_mode ? "via OS keychain" : "via .env (dev mode)"}
        </span>
      </div>
      <div className="grid gap-0">
        {snapshot.secret_keys.map((row) => (
          <div
            key={row.name}
            className="flex items-center justify-between gap-3 border-b border-hair py-2.5 last:border-0"
          >
            <div className="min-w-0">
              <div className="text-[13px] text-fg-1">
                {SECRET_LABEL[row.name] ?? row.name}
              </div>
              <div className="mt-0.5 font-mono text-[11px] text-fg-4">
                {row.configured
                  ? `••••${row.last_four ?? ""}`
                  : "Not set"}
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <Button size="sm" onClick={() => setEditingKey(row.name)}>
                {row.configured ? "Replace" : "Set"}
              </Button>
              {row.configured && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={async () => {
                    await apiFetch(`/settings/secrets/${row.name}`, {
                      method: "DELETE",
                    });
                    await onChange();
                  }}
                >
                  Clear
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>

      {editingKey && (
        <SetSecretModal
          name={editingKey}
          label={SECRET_LABEL[editingKey] ?? editingKey}
          onClose={() => setEditingKey(null)}
          onSaved={closeAndRefresh}
        />
      )}
    </Card>
  );
}

function SetSecretModal({
  name,
  label,
  onClose,
  onSaved,
}: {
  name: string;
  label: string;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (!value) return;
    setSaving(true);
    setErr(null);
    try {
      await apiFetch(`/settings/secrets/${name}`, {
        method: "PUT",
        body: JSON.stringify({ value }),
      });
      await onSaved();
    } catch (e) {
      setErr(String(e));
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-lg border border-hair bg-bg-1 p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3">
          <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
            Set
          </div>
          <div className="mt-1 text-[15px] text-fg-0">{label}</div>
        </div>

        {err && (
          <div className="mb-3 rounded-md border border-err/30 bg-err-soft p-3 text-xs text-[oklch(90%_0.12_25)]">
            {err}
          </div>
        )}

        <input
          type="password"
          autoFocus
          autoComplete="off"
          spellCheck={false}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
            if (e.key === "Escape") onClose();
          }}
          placeholder="Paste the secret value…"
          className="w-full rounded-md border border-hair bg-white/[0.03] px-3 py-2 font-mono text-[13px] text-fg-0 outline-none focus:border-hair-strong"
        />

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={submit}
            disabled={!value || saving}
          >
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Provider routing
// ---------------------------------------------------------------------------

function ProvidersCard({
  snapshot,
  onChange,
}: {
  snapshot: SettingsSnapshot;
  onChange: () => Promise<void>;
}) {
  const [saving, setSaving] = useState<string | null>(null);

  const update = async (
    field: keyof SettingsSnapshot["providers"],
    value: string,
  ) => {
    setSaving(field);
    try {
      // The backend payload field is `<field>_provider` for the four
      // creative roles and `renderer_backend` for the renderer.
      const apiField =
        field === "renderer" ? "renderer_backend" : `${field}_provider`;
      await apiFetch("/settings/providers", {
        method: "PUT",
        body: JSON.stringify({ [apiField]: value }),
      });
      await onChange();
    } finally {
      setSaving(null);
    }
  };

  return (
    <Card>
      <div className="mb-3 font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
        Provider routing
      </div>
      <div className="grid gap-2.5">
        {(
          Object.keys(PROVIDER_OPTIONS) as Array<
            keyof SettingsSnapshot["providers"]
          >
        ).map((field) => (
          <div
            key={field}
            className="flex items-center justify-between gap-3 border-b border-hair py-2 last:border-0"
          >
            <div className="text-[13px] text-fg-1">
              {field === "renderer" ? "Video renderer" : `${field[0].toUpperCase()}${field.slice(1)} provider`}
            </div>
            <div className="flex items-center gap-2">
              <select
                disabled={saving === field}
                value={snapshot.providers[field]}
                onChange={(e) => update(field, e.target.value)}
                className="rounded-md border border-hair bg-white/[0.03] px-2.5 py-1.5 text-[13px] text-fg-0 outline-none focus:border-hair-strong disabled:opacity-50"
              >
                {PROVIDER_OPTIONS[field].map((opt) => (
                  <option key={opt} value={opt}>
                    {PROVIDER_LABEL[opt] ?? opt}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Cost UI — unchanged from pre-A6.
// ---------------------------------------------------------------------------

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
