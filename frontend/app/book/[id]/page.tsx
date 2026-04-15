"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";

type Package = {
  id: number;
  revision_number: number;
  script: string;
  visual_prompts: string[];
  narration: string;
  titles: Record<string, string>;
  hashtags: Record<string, string[]>;
  affiliate_amazon: string | null;
  affiliate_bookshop: string | null;
  regenerate_note: string | null;
  is_approved: boolean;
  created_at: string | null;
};

type BookDetail = {
  id: number;
  title: string;
  author: string;
  isbn: string | null;
  genre: string | null;
  genre_override: string | null;
  status: string;
  packages: Package[];
};

const PLATFORMS: Array<{ key: string; label: string }> = [
  { key: "tiktok", label: "TikTok" },
  { key: "yt_shorts", label: "YouTube Shorts" },
  { key: "ig_reels", label: "Instagram Reels" },
  { key: "threads", label: "Threads" },
];

export default function BookReviewPage({
  params,
}: {
  params: { id: string };
}) {
  const [book, setBook] = useState<BookDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [generating, setGenerating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [regenNote, setRegenNote] = useState("");

  const refresh = async () => {
    setError(null);
    try {
      const data = await apiFetch<BookDetail>(`/books/${params.id}`);
      setBook(data);
      // Snap to the latest revision unless the user picked one already.
      setActiveId((prev) => prev ?? data.packages[0]?.id ?? null);
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  const generatePackage = async (note?: string) => {
    setGenerating(true);
    setError(null);
    try {
      const res = await apiFetch<{ package_id: number; revision_number: number }>(
        `/books/${params.id}/generate`,
        { method: "POST", body: JSON.stringify({ note: note ?? null }) },
      );
      setActiveId(res.package_id); // jump to the new revision
      setRegenNote("");
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setGenerating(false);
    }
  };

  const approve = async (packageId: number) => {
    setApproving(true);
    setError(null);
    try {
      await apiFetch(`/packages/${packageId}/approve`, { method: "POST" });
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setApproving(false);
    }
  };

  const [rendering, setRendering] = useState(false);
  const [lastRender, setLastRender] = useState<{
    file_path: string;
    duration_seconds: number;
    size_bytes: number;
    tone: string;
  } | null>(null);

  const render = async (packageId: number) => {
    setRendering(true);
    setError(null);
    setLastRender(null);
    try {
      const res = await apiFetch<{
        package_id: number;
        file_path: string;
        duration_seconds: number;
        size_bytes: number;
        tone: string;
      }>(`/packages/${packageId}/render`, { method: "POST" });
      setLastRender(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setRendering(false);
    }
  };

  if (!book) {
    return (
      <main className="mx-auto max-w-6xl p-8">
        <Link href="/dashboard" className="text-sm opacity-70 hover:underline">
          ← Queue
        </Link>
        <p className="mt-6 text-sm opacity-70">
          {error ? `Error: ${error}` : "Loading…"}
        </p>
      </main>
    );
  }

  const effectiveGenre = book.genre_override || book.genre || "uncategorized";
  const active = book.packages.find((p) => p.id === activeId) ?? book.packages[0] ?? null;

  return (
    <main className="mx-auto max-w-6xl p-8">
      <Link href="/dashboard" className="text-sm opacity-70 hover:underline">
        ← Queue
      </Link>
      <header className="mt-2 mb-8">
        <h1 className="text-3xl font-semibold">{book.title}</h1>
        <p className="mt-1 text-sm opacity-70">
          {book.author} · <span className="italic">{effectiveGenre}</span> · status:{" "}
          <code>{book.status}</code>
        </p>
      </header>

      {error && (
        <div className="mb-6 rounded-md border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      {book.packages.length === 0 ? (
        <div className="rounded-lg border border-white/10 p-8 text-center">
          <p className="mb-4 text-sm opacity-70">No content package yet.</p>
          <button
            onClick={() => generatePackage()}
            disabled={generating}
            className="rounded-md bg-white/10 px-4 py-2 text-sm hover:bg-white/20 disabled:opacity-50"
          >
            {generating ? "Generating…" : "Generate Package"}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_240px]">
          <div>
            {active && (
              <PackageView
                pkg={active}
                onApprove={approve}
                approving={approving}
                onRender={render}
                rendering={rendering}
                lastRender={lastRender}
              />
            )}
            <RegenerateForm
              note={regenNote}
              setNote={setRegenNote}
              onSubmit={() => generatePackage(regenNote || undefined)}
              generating={generating}
            />
          </div>
          <aside>
            <RevisionHistory
              packages={book.packages}
              activeId={active?.id ?? null}
              onSelect={setActiveId}
            />
          </aside>
        </div>
      )}
    </main>
  );
}

// ---------------------------------------------------------------------------

function PackageView({
  pkg,
  onApprove,
  approving,
  onRender,
  rendering,
  lastRender,
}: {
  pkg: Package;
  onApprove: (id: number) => void;
  approving: boolean;
  onRender: (id: number) => void;
  rendering: boolean;
  lastRender: {
    file_path: string;
    duration_seconds: number;
    size_bytes: number;
    tone: string;
  } | null;
}) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm">
          <span className="opacity-70">Revision {pkg.revision_number}</span>
          {pkg.is_approved && (
            <span className="ml-2 rounded-full bg-green-500/20 px-2 py-0.5 text-xs text-green-200">
              approved
            </span>
          )}
          {pkg.regenerate_note && (
            <div className="mt-1 text-xs opacity-60">
              note: &ldquo;{pkg.regenerate_note}&rdquo;
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {pkg.is_approved && (
            <button
              onClick={() => onRender(pkg.id)}
              disabled={rendering}
              className="rounded-md bg-white/10 px-4 py-2 text-sm hover:bg-white/20 disabled:opacity-50"
              title="Synthesize narration, generate images, render mp4"
            >
              {rendering ? "Rendering…" : "Render Video"}
            </button>
          )}
          {!pkg.is_approved && (
            <button
              onClick={() => onApprove(pkg.id)}
              disabled={approving}
              className="rounded-md bg-green-500/20 px-4 py-2 text-sm text-green-100 hover:bg-green-500/30 disabled:opacity-50"
            >
              {approving ? "Approving…" : "Approve"}
            </button>
          )}
        </div>
      </div>

      {lastRender && (
        <div className="rounded-lg border border-green-500/30 bg-green-500/5 p-4 text-sm">
          <div className="mb-2 opacity-80">
            Rendered {lastRender.duration_seconds.toFixed(1)}s · {(lastRender.size_bytes / 1_048_576).toFixed(1)} MB · tone={lastRender.tone}
          </div>
          <code className="text-xs opacity-70">{lastRender.file_path}</code>
        </div>
      )}

      <Section title="90-sec script" copyText={pkg.script}>
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{pkg.script}</p>
      </Section>

      <Section title={`Image prompts (${pkg.visual_prompts.length})`}>
        <div className="space-y-3">
          {pkg.visual_prompts.map((prompt, i) => (
            <div
              key={i}
              className="flex items-start justify-between gap-3 rounded-md border border-white/5 bg-white/5 p-3"
            >
              <div className="flex-1 text-sm">
                <span className="mr-2 opacity-60">#{i + 1}</span>
                {prompt}
              </div>
              <CopyButton text={prompt} />
            </div>
          ))}
        </div>
      </Section>

      <Section title="Narration (TTS-ready)" copyText={pkg.narration}>
        <p className="whitespace-pre-wrap text-sm leading-relaxed">
          {pkg.narration}
        </p>
      </Section>

      <Section title="Per-platform meta">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {PLATFORMS.map(({ key, label }) => {
            const title = pkg.titles?.[key] ?? "—";
            const hashtags = pkg.hashtags?.[key] ?? [];
            const hashtagStr = hashtags.join(" ");
            return (
              <div
                key={key}
                className="rounded-md border border-white/5 bg-white/5 p-4"
              >
                <h3 className="mb-3 text-sm font-medium">{label}</h3>
                <div className="mb-3">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-xs opacity-60">Title</span>
                    <CopyButton text={title} />
                  </div>
                  <p className="text-sm">{title}</p>
                </div>
                <div>
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-xs opacity-60">
                      Hashtags ({hashtags.length})
                    </span>
                    <CopyButton text={hashtagStr} />
                  </div>
                  <p className="text-sm opacity-80">{hashtagStr || "—"}</p>
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      <Section title="Affiliate links">
        <div className="space-y-2">
          {pkg.affiliate_amazon ? (
            <AffiliateRow label="Amazon" url={pkg.affiliate_amazon} />
          ) : null}
          {pkg.affiliate_bookshop ? (
            <AffiliateRow label="Bookshop" url={pkg.affiliate_bookshop} />
          ) : null}
          {!pkg.affiliate_amazon && !pkg.affiliate_bookshop && (
            <p className="text-xs opacity-60">
              No affiliate keys configured (AMAZON_ASSOCIATE_TAG / BOOKSHOP_AFFILIATE_ID).
            </p>
          )}
        </div>
      </Section>
    </div>
  );
}

function Section({
  title,
  copyText,
  children,
}: {
  title: string;
  copyText?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-white/10 p-6">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-medium">{title}</h2>
        {copyText !== undefined && <CopyButton text={copyText} />}
      </div>
      {children}
    </section>
  );
}

function AffiliateRow({ label, url }: { label: string; url: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 text-xs opacity-60">{label}</span>
      <code className="flex-1 truncate text-xs">{url}</code>
      <CopyButton text={url} />
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const onClick = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard may be blocked — swallow */
    }
  };
  return (
    <button
      onClick={onClick}
      className="rounded-md bg-white/10 px-2 py-1 text-xs hover:bg-white/20"
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function RegenerateForm({
  note,
  setNote,
  onSubmit,
  generating,
}: {
  note: string;
  setNote: (v: string) => void;
  onSubmit: () => void;
  generating: boolean;
}) {
  return (
    <section className="mt-6 rounded-lg border border-white/10 p-6">
      <h2 className="mb-3 font-medium">Regenerate</h2>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder='Optional: tell Claude how to change it. "Make the hook darker." "Less dramatic." "More social proof."'
        className="mb-3 h-24 w-full rounded-md border border-white/10 bg-transparent p-3 text-sm"
      />
      <button
        onClick={onSubmit}
        disabled={generating}
        className="rounded-md bg-white/10 px-4 py-2 text-sm hover:bg-white/20 disabled:opacity-50"
      >
        {generating ? "Generating…" : note ? "Regenerate with note" : "Regenerate"}
      </button>
    </section>
  );
}

function RevisionHistory({
  packages,
  activeId,
  onSelect,
}: {
  packages: Package[];
  activeId: number | null;
  onSelect: (id: number) => void;
}) {
  return (
    <div className="lg:sticky lg:top-8">
      <h3 className="mb-3 text-sm font-medium opacity-70">History</h3>
      <ul className="space-y-1">
        {packages.map((p) => (
          <li key={p.id}>
            <button
              onClick={() => onSelect(p.id)}
              className={`w-full rounded-md px-3 py-2 text-left text-sm transition ${
                p.id === activeId ? "bg-white/10" : "hover:bg-white/5"
              }`}
            >
              <div className="flex items-center justify-between">
                <span>Rev {p.revision_number}</span>
                {p.is_approved && (
                  <span className="rounded-full bg-green-500/20 px-1.5 py-0.5 text-xs text-green-200">
                    ✓
                  </span>
                )}
              </div>
              {p.regenerate_note && (
                <div className="mt-1 truncate text-xs opacity-60">
                  &ldquo;{p.regenerate_note}&rdquo;
                </div>
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
