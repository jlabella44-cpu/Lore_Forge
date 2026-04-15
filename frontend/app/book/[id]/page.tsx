"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { apiFetch, rendersUrl } from "@/lib/api";

type HookAlternative = { angle: string; text: string };

type Scene = {
  section: string;
  prompt: string;
  focus: string;
};

type CaptionWord = {
  word: string;
  start: number;
  end: number;
};

type Package = {
  id: number;
  revision_number: number;
  script: string;
  narration: string;
  hook_alternatives: HookAlternative[] | null;
  chosen_hook_index: number | null;
  visual_prompts: Scene[] | null;
  section_word_counts: Record<string, number> | null;
  captions: CaptionWord[] | null;
  titles: Record<string, string>;
  hashtags: Record<string, string[]>;
  affiliate_amazon: string | null;
  affiliate_bookshop: string | null;
  regenerate_note: string | null;
  is_approved: boolean;
  created_at: string | null;
};

const SECTION_LABEL: Record<string, string> = {
  hook: "Hook",
  world_tease: "World tease",
  emotional_pull: "Emotional pull",
  social_proof: "Social proof",
  cta: "CTA",
};

const ANGLE_LABEL: Record<string, string> = {
  curiosity: "Curiosity",
  fear: "Fear",
  promise: "Promise",
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

  const [publishing, setPublishing] = useState<string | null>(null);
  const [published, setPublished] = useState<
    Record<string, { external_id: string; published_at: string } | { error: string }>
  >({});

  const publish = async (packageId: number, platform: string) => {
    setPublishing(platform);
    setError(null);
    try {
      const res = await apiFetch<{
        video_id: number;
        platform: string;
        external_id: string;
        published_at: string;
      }>(`/publish/${packageId}/${platform}`, { method: "POST" });
      setPublished((prev) => ({ ...prev, [platform]: res }));
      await refresh(); // book.status → "published"
    } catch (e) {
      setPublished((prev) => ({ ...prev, [platform]: { error: String(e) } }));
    } finally {
      setPublishing(null);
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
                onPublish={publish}
                publishing={publishing}
                published={published}
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

const PUBLISH_TARGETS: Array<{ key: string; label: string }> = [
  { key: "yt_shorts", label: "YouTube Shorts" },
  { key: "tiktok", label: "TikTok" },
  { key: "ig_reels", label: "Instagram Reels" },
  { key: "threads", label: "Threads" },
];

type PublishStatus =
  | { external_id: string; published_at: string }
  | { error: string };

function PackageView({
  pkg,
  onApprove,
  approving,
  onRender,
  rendering,
  lastRender,
  onPublish,
  publishing,
  published,
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
  onPublish: (id: number, platform: string) => void;
  publishing: string | null;
  published: Record<string, PublishStatus>;
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
        <div className="space-y-3 rounded-lg border border-green-500/30 bg-green-500/5 p-4 text-sm">
          <div className="opacity-80">
            Rendered {lastRender.duration_seconds.toFixed(1)}s · {(lastRender.size_bytes / 1_048_576).toFixed(1)} MB · tone={lastRender.tone}
          </div>
          {/* Inline preview via the backend's /renders static mount. */}
          <video
            key={`${pkg.id}-${lastRender.size_bytes}`}
            src={rendersUrl(pkg.id)}
            controls
            playsInline
            className="w-full max-w-[360px] rounded-md border border-white/10 bg-black"
            style={{ aspectRatio: "9 / 16" }}
          />
          <code className="block text-xs opacity-70">{lastRender.file_path}</code>

          <div className="border-t border-green-500/20 pt-3">
            <div className="mb-2 text-xs font-medium opacity-70">Publish (manual-approve gate)</div>
            <div className="flex flex-wrap gap-2">
              {PUBLISH_TARGETS.map(({ key, label }) => {
                const status = published[key];
                const isPublishing = publishing === key;
                const succeeded = status && !("error" in status);
                return (
                  <div key={key} className="flex flex-col gap-1">
                    <button
                      onClick={() => onPublish(pkg.id, key)}
                      disabled={isPublishing || !!succeeded}
                      className={`rounded-md px-3 py-1.5 text-xs disabled:opacity-50 ${
                        succeeded
                          ? "bg-green-500/30 text-green-100"
                          : "bg-white/10 hover:bg-white/20"
                      }`}
                    >
                      {succeeded
                        ? `✓ ${label}`
                        : isPublishing
                          ? `Uploading to ${label}…`
                          : label}
                    </button>
                    {status && "error" in status && (
                      <div
                        className="max-w-xs truncate text-xs text-red-200"
                        title={status.error}
                      >
                        {status.error}
                      </div>
                    )}
                    {succeeded && (
                      <div className="text-xs opacity-60">
                        id: {status.external_id}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <Section title="90-sec script" copyText={pkg.script}>
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{pkg.script}</p>
      </Section>

      {pkg.hook_alternatives && pkg.hook_alternatives.length > 0 && (
        <Section title="Hook portfolio">
          <ul className="space-y-2">
            {pkg.hook_alternatives.map((h, i) => {
              const isChosen = i === pkg.chosen_hook_index;
              return (
                <li
                  key={i}
                  className={`flex items-start justify-between gap-3 rounded-md border p-3 ${
                    isChosen
                      ? "border-green-500/40 bg-green-500/5"
                      : "border-white/5 bg-white/5"
                  }`}
                >
                  <div className="flex-1 text-sm">
                    <span className="mr-2 rounded-full bg-white/10 px-2 py-0.5 text-xs uppercase tracking-wider opacity-70">
                      {ANGLE_LABEL[h.angle] ?? h.angle}
                    </span>
                    {isChosen && (
                      <span className="mr-2 rounded-full bg-green-500/20 px-2 py-0.5 text-xs text-green-200">
                        chosen
                      </span>
                    )}
                    <span>{h.text}</span>
                  </div>
                  <CopyButton text={h.text} />
                </li>
              );
            })}
          </ul>
        </Section>
      )}

      <Section
        title={`Image prompts (${pkg.visual_prompts?.length ?? 0})`}
      >
        <div className="space-y-3">
          {(pkg.visual_prompts ?? []).map((scene, i) => (
            <div
              key={i}
              className="flex items-start justify-between gap-3 rounded-md border border-white/5 bg-white/5 p-3"
            >
              <div className="flex-1 text-sm">
                <div className="mb-1 text-xs opacity-60">
                  <span className="mr-2 rounded-full bg-white/10 px-2 py-0.5">
                    {SECTION_LABEL[scene.section] ?? scene.section}
                  </span>
                  {scene.focus && <span>{scene.focus}</span>}
                </div>
                {scene.prompt}
              </div>
              <CopyButton text={scene.prompt} />
            </div>
          ))}
        </div>
      </Section>

      <Section title="Narration (TTS-ready)" copyText={pkg.narration}>
        <p className="whitespace-pre-wrap text-sm leading-relaxed">
          {pkg.narration}
        </p>
        {pkg.captions && pkg.captions.length > 0 && (
          <CaptionsPreview captions={pkg.captions} />
        )}
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

function CaptionsPreview({ captions }: { captions: CaptionWord[] }) {
  const [expanded, setExpanded] = useState(false);
  const durationSeconds = captions[captions.length - 1]?.end ?? 0;
  const preview = captions
    .slice(0, 14)
    .map((c) => c.word)
    .join(" ");
  const full = captions.map((c) => `${c.word}`).join(" ");

  return (
    <div className="mt-4 rounded-md border border-white/5 bg-white/5 p-3 text-xs">
      <div className="mb-2 flex items-center justify-between">
        <div className="opacity-70">
          Captions — {captions.length} words,{" "}
          {durationSeconds.toFixed(1)}s (word-level, Whisper)
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="rounded-md bg-white/10 px-2 py-1 hover:bg-white/20"
          >
            {expanded ? "Collapse" : "Show all"}
          </button>
          <CopyButton text={full} />
        </div>
      </div>
      {expanded ? (
        <ol className="max-h-64 space-y-0.5 overflow-y-auto font-mono text-[11px] opacity-80">
          {captions.map((c, i) => (
            <li key={i}>
              <span className="inline-block w-16 opacity-60 tabular-nums">
                {c.start.toFixed(2)}s
              </span>
              {c.word}
            </li>
          ))}
        </ol>
      ) : (
        <p className="italic opacity-75">
          {preview}
          {captions.length > 14 ? "…" : ""}
        </p>
      )}
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
