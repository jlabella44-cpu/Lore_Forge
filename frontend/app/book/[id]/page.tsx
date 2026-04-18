"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { apiFetch, CostSummary, dollars, pollJob, rendersUrl } from "@/lib/api";

type HookAlternative = { angle: string; text: string };

type Scene = {
  section?: string;
  label?: string;
  // Back-compat: older packages have `prompt: string`; new ones use `prompts: string[]`.
  prompt?: string;
  prompts?: string[];
  focus: string;
};

function scenePrompts(scene: Scene): string[] {
  if (scene.prompts && scene.prompts.length > 0) return scene.prompts;
  if (scene.prompt) return [scene.prompt];
  return [];
}

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
  dossier: Record<string, unknown> | null;
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

  const [costs, setCosts] = useState<CostSummary | null>(null);

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
    // Cost lookup is best-effort; don't fail the page if it breaks.
    apiFetch<CostSummary>("/analytics/cost?days=365")
      .then(setCosts)
      .catch(() => {});
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  const [generateStage, setGenerateStage] = useState<string | null>(null);

  const generatePackage = async (note?: string) => {
    setGenerating(true);
    setGenerateStage("queued");
    setError(null);
    try {
      const queued = await apiFetch<{ job_id: number; status: string }>(
        `/books/${params.id}/generate?async=true`,
        { method: "POST", body: JSON.stringify({ note: note ?? null }) },
      );
      const job = await pollJob(queued.job_id, (j) =>
        setGenerateStage(j.message ?? j.status),
      );
      if (job.status === "failed") {
        throw new Error(job.error ?? "Generation failed");
      }
      const result = job.result as {
        package_id: number;
        revision_number: number;
      };
      setActiveId(result.package_id);
      setRegenNote("");
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setGenerating(false);
      setGenerateStage(null);
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
  const [renderStage, setRenderStage] = useState<string | null>(null);
  const [lastRender, setLastRender] = useState<{
    file_path: string;
    duration_seconds: number;
    size_bytes: number;
    tone: string;
  } | null>(null);

  const render = async (packageId: number) => {
    setRendering(true);
    setRenderStage("queued");
    setError(null);
    setLastRender(null);
    try {
      const queued = await apiFetch<{ job_id: number; status: string }>(
        `/packages/${packageId}/render?async=true`,
        { method: "POST" },
      );
      const job = await pollJob(queued.job_id, (j) =>
        setRenderStage(j.message ?? j.status),
      );
      if (job.status === "failed") {
        throw new Error(job.error ?? "Render failed");
      }
      setLastRender(
        job.result as {
          package_id: number;
          file_path: string;
          duration_seconds: number;
          size_bytes: number;
          tone: string;
        },
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setRendering(false);
      setRenderStage(null);
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

      <DossierEditor
        bookId={book.id}
        dossier={book.dossier}
        onSaved={refresh}
      />

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
                renderStage={renderStage}
                lastRender={lastRender}
                onPublish={publish}
                publishing={publishing}
                published={published}
                onRefresh={refresh}
                costCents={
                  costs?.per_package.find((p) => p.package_id === active.id)
                    ?.cents ?? null
                }
              />
            )}
            <RegenerateForm
              note={regenNote}
              setNote={setRegenNote}
              onSubmit={() => generatePackage(regenNote || undefined)}
              generating={generating}
              generateStage={generateStage}
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
  renderStage,
  lastRender,
  onPublish,
  publishing,
  published,
  onRefresh,
  costCents,
}: {
  pkg: Package;
  onApprove: (id: number) => void;
  approving: boolean;
  onRender: (id: number) => void;
  rendering: boolean;
  renderStage: string | null;
  lastRender: {
    file_path: string;
    duration_seconds: number;
    size_bytes: number;
    tone: string;
  } | null;
  onPublish: (id: number, platform: string) => void;
  publishing: string | null;
  published: Record<string, PublishStatus>;
  onRefresh: () => Promise<void> | void;
  costCents: number | null;
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
          {costCents !== null && costCents > 0 && (
            <span
              title="Total spent on LLM + TTS + images + Whisper calls for this revision"
              className="ml-2 rounded-full bg-white/10 px-2 py-0.5 text-xs tabular-nums"
            >
              {dollars(costCents)} spent
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
              {rendering
                ? `Rendering… ${renderStage ?? ""}`.trim()
                : "Render Video"}
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

      {(lastRender || pkg.is_approved) && (
        <div className="space-y-3 rounded-lg border border-green-500/30 bg-green-500/5 p-4 text-sm">
          {lastRender ? (
            <div className="opacity-80">
              Rendered {lastRender.duration_seconds.toFixed(1)}s · {(lastRender.size_bytes / 1_048_576).toFixed(1)} MB · tone={lastRender.tone}
            </div>
          ) : (
            <div className="opacity-70">
              Preview of previously rendered mp4 (404s if the package hasn&apos;t been rendered yet).
            </div>
          )}
          {/* Inline preview via the backend's /renders static mount.
              `key` forces a reload after a fresh render overwrites the file. */}
          <video
            key={`${pkg.id}-${lastRender?.size_bytes ?? "seed"}`}
            src={rendersUrl(pkg.id)}
            controls
            playsInline
            className="w-full max-w-[360px] rounded-md border border-white/10 bg-black"
            style={{ aspectRatio: "9 / 16" }}
          />
          {lastRender && (
            <code className="block text-xs opacity-70">{lastRender.file_path}</code>
          )}

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

      <EditableScriptSection pkg={pkg} onRefresh={onRefresh} />

      {pkg.hook_alternatives && pkg.hook_alternatives.length > 0 && (
        <HookPortfolio pkg={pkg} onRefresh={onRefresh} />
      )}

      <EditableScenesSection pkg={pkg} onRefresh={onRefresh} />

      <Section title="Narration (TTS-ready)" copyText={pkg.narration}>
        <p className="whitespace-pre-wrap text-sm leading-relaxed">
          {pkg.narration}
        </p>
        {pkg.captions && pkg.captions.length > 0 && (
          <CaptionsPreview captions={pkg.captions} />
        )}
      </Section>

      <EditablePlatformMetaSection pkg={pkg} onRefresh={onRefresh} />

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
  generateStage,
}: {
  note: string;
  setNote: (v: string) => void;
  onSubmit: () => void;
  generating: boolean;
  generateStage: string | null;
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
      <div className="flex items-center gap-3">
        <button
          onClick={onSubmit}
          disabled={generating}
          className="rounded-md bg-white/10 px-4 py-2 text-sm hover:bg-white/20 disabled:opacity-50"
        >
          {generating ? "Generating…" : note ? "Regenerate with note" : "Regenerate"}
        </button>
        {generating && generateStage && (
          <span className="text-xs opacity-70">{generateStage}</span>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Package field editors — PATCH /packages/{id} for hand-edits without a
// full regenerate. Edits to `script` and `visual_prompts` flip the
// package's `needs_rerender` flag on the server; the book status/UI
// already reacts to that.
// ---------------------------------------------------------------------------

async function patchPackage(
  id: number,
  body: Record<string, unknown>,
): Promise<void> {
  await apiFetch(`/packages/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

function EditableScriptSection({
  pkg,
  onRefresh,
}: {
  pkg: Package;
  onRefresh: () => Promise<void> | void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = () => {
    setDraft(pkg.script);
    setError(null);
    setEditing(true);
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await patchPackage(pkg.id, { script: draft });
      await onRefresh();
      setEditing(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="rounded-lg border border-white/10 p-6">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-medium">90-sec script</h2>
        <div className="flex items-center gap-2">
          {!editing && <CopyButton text={pkg.script} />}
          {!editing ? (
            <button
              onClick={startEdit}
              className="rounded-md bg-white/10 px-3 py-1 text-xs hover:bg-white/20"
            >
              Edit
            </button>
          ) : null}
        </div>
      </div>

      {!editing ? (
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{pkg.script}</p>
      ) : (
        <div className="space-y-3">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            spellCheck={false}
            className="h-96 w-full rounded-md border border-white/10 bg-black/40 p-3 font-mono text-xs leading-relaxed"
          />
          {error && <p className="text-xs text-red-200">Save failed: {error}</p>}
          <p className="text-xs opacity-60">
            Script must contain all five section headers (## HOOK, ## WORLD TEASE,
            ## EMOTIONAL PULL, ## SOCIAL PROOF, ## CTA). Saving flags the package
            for re-render — narration and the existing mp4 are stale until you
            click Render.
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={save}
              disabled={saving}
              className="rounded-md bg-green-500/20 px-3 py-1.5 text-sm text-green-100 hover:bg-green-500/30 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              onClick={() => setEditing(false)}
              disabled={saving}
              className="rounded-md bg-white/10 px-3 py-1.5 text-sm hover:bg-white/20 disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function HookPortfolio({
  pkg,
  onRefresh,
}: {
  pkg: Package;
  onRefresh: () => Promise<void> | void;
}) {
  const [pendingIndex, setPendingIndex] = useState<number | null>(null);
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);

  const choose = async (i: number) => {
    if (i === pkg.chosen_hook_index) return;
    setPendingIndex(i);
    try {
      await patchPackage(pkg.id, { chosen_hook_index: i });
      await onRefresh();
    } finally {
      setPendingIndex(null);
    }
  };

  const applyToScript = async () => {
    setApplying(true);
    setApplyError(null);
    try {
      await apiFetch(`/packages/${pkg.id}/apply-chosen-hook`, {
        method: "POST",
      });
      await onRefresh();
    } catch (e) {
      setApplyError(String(e));
    } finally {
      setApplying(false);
    }
  };

  const chosenText =
    pkg.chosen_hook_index !== null
      ? pkg.hook_alternatives?.[pkg.chosen_hook_index]?.text
      : undefined;
  // The ## HOOK block's first line (pkg.script) — if it matches the chosen
  // alternative's text the Apply button has nothing useful to do.
  const hookInSync =
    !!chosenText &&
    !!pkg.script &&
    pkg.script
      .replace(/^#+\s*HOOK\s*:?\s*\n?/i, "")
      .trimStart()
      .startsWith(chosenText.trim());

  return (
    <Section title="Hook portfolio">
      <div className="mb-3 flex items-start justify-between gap-3">
        <p className="flex-1 text-xs opacity-60">
          Click an alternative to make it the chosen hook. Swapping only
          updates metadata — use &ldquo;Apply to script&rdquo; to deterministically
          rewrite the script&apos;s ## HOOK line with the chosen hook text.
        </p>
        {pkg.hook_alternatives && pkg.hook_alternatives.length > 0 && (
          <button
            onClick={applyToScript}
            disabled={applying || hookInSync || pendingIndex !== null}
            title={
              hookInSync
                ? "Script's ## HOOK already matches the chosen alternative"
                : "Rewrite the script's ## HOOK block with the chosen hook text"
            }
            className="shrink-0 rounded-md bg-white/10 px-3 py-1 text-xs hover:bg-white/20 disabled:opacity-40"
          >
            {applying ? "Applying…" : "Apply to script"}
          </button>
        )}
      </div>
      {applyError && (
        <p className="mb-3 text-xs text-red-200">Apply failed: {applyError}</p>
      )}
      <ul className="space-y-2">
        {(pkg.hook_alternatives ?? []).map((h, i) => {
          const isChosen = i === pkg.chosen_hook_index;
          const isPending = pendingIndex === i;
          return (
            <li
              key={i}
              className={`flex items-start justify-between gap-3 rounded-md border p-3 ${
                isChosen
                  ? "border-green-500/40 bg-green-500/5"
                  : "border-white/5 bg-white/5"
              }`}
            >
              <label className="flex flex-1 cursor-pointer items-start gap-3 text-sm">
                <input
                  type="radio"
                  name={`hook-choice-${pkg.id}`}
                  checked={isChosen}
                  onChange={() => choose(i)}
                  disabled={pendingIndex !== null}
                  className="mt-1"
                />
                <span className="flex-1">
                  <span className="mr-2 rounded-full bg-white/10 px-2 py-0.5 text-xs uppercase tracking-wider opacity-70">
                    {ANGLE_LABEL[h.angle] ?? h.angle}
                  </span>
                  {isChosen && (
                    <span className="mr-2 rounded-full bg-green-500/20 px-2 py-0.5 text-xs text-green-200">
                      chosen
                    </span>
                  )}
                  {isPending && (
                    <span className="mr-2 rounded-full bg-white/10 px-2 py-0.5 text-xs opacity-70">
                      saving…
                    </span>
                  )}
                  <span>{h.text}</span>
                </span>
              </label>
              <CopyButton text={h.text} />
            </li>
          );
        })}
      </ul>
    </Section>
  );
}

function EditableScenesSection({
  pkg,
  onRefresh,
}: {
  pkg: Package;
  onRefresh: () => Promise<void> | void;
}) {
  const scenes = pkg.visual_prompts ?? [];
  const totalPrompts = scenes.reduce((n, s) => n + scenePrompts(s).length, 0);

  return (
    <Section
      title={`Image prompts (${totalPrompts} across ${scenes.length} sections)`}
    >
      <div className="space-y-3">
        {scenes.map((scene, i) => (
          <EditableSceneRow
            key={i}
            pkg={pkg}
            sceneIndex={i}
            onRefresh={onRefresh}
          />
        ))}
      </div>
    </Section>
  );
}

function EditableSceneRow({
  pkg,
  sceneIndex,
  onRefresh,
}: {
  pkg: Package;
  sceneIndex: number;
  onRefresh: () => Promise<void> | void;
}) {
  const scene = (pkg.visual_prompts ?? [])[sceneIndex];
  const prompts = scenePrompts(scene);
  const sectionKey = scene.section ?? scene.label ?? "";

  const [editing, setEditing] = useState(false);
  const [drafts, setDrafts] = useState<string[]>(prompts);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = () => {
    setDrafts(prompts);
    setError(null);
    setEditing(true);
  };

  const save = async () => {
    const cleaned = drafts.map((p) => p.trim()).filter((p) => p.length > 0);
    if (cleaned.length === 0) {
      setError("At least one prompt is required.");
      return;
    }
    const allScenes = (pkg.visual_prompts ?? []).map((s, i) =>
      i === sceneIndex
        ? { ...s, prompts: cleaned, prompt: undefined }
        : s,
    );
    setSaving(true);
    setError(null);
    try {
      await patchPackage(pkg.id, { visual_prompts: allScenes });
      await onRefresh();
      setEditing(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-md border border-white/5 bg-white/5 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="text-xs opacity-60">
          <span className="mr-2 rounded-full bg-white/10 px-2 py-0.5">
            {SECTION_LABEL[sectionKey] ?? sectionKey}
          </span>
          {prompts.length > 1 && (
            <span className="mr-2 rounded-full bg-emerald-500/20 px-2 py-0.5 text-emerald-200">
              {prompts.length} images
            </span>
          )}
          {scene.focus && <span>{scene.focus}</span>}
        </div>
        {!editing && (
          <button
            onClick={startEdit}
            className="rounded-md bg-white/10 px-2 py-1 text-xs hover:bg-white/20"
          >
            Edit
          </button>
        )}
      </div>

      {!editing ? (
        <div className="space-y-2">
          {prompts.map((prompt, j) => (
            <div
              key={j}
              className="flex items-start justify-between gap-3 text-sm"
            >
              <div className="flex-1 border-l border-white/10 pl-3">
                {prompts.length > 1 && (
                  <span className="mr-2 text-xs opacity-40">#{j + 1}</span>
                )}
                {prompt}
              </div>
              <CopyButton text={prompt} />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {drafts.map((draft, j) => (
            <textarea
              key={j}
              value={draft}
              onChange={(e) =>
                setDrafts((ds) =>
                  ds.map((d, k) => (k === j ? e.target.value : d)),
                )
              }
              spellCheck={false}
              className="h-20 w-full rounded-md border border-white/10 bg-black/40 p-2 font-mono text-xs leading-relaxed"
            />
          ))}
          <div className="flex items-center gap-2">
            <button
              onClick={() =>
                setDrafts((ds) => [...ds, ""])
              }
              className="rounded-md bg-white/10 px-2 py-1 text-xs hover:bg-white/20"
            >
              + prompt
            </button>
            {drafts.length > 1 && (
              <button
                onClick={() => setDrafts((ds) => ds.slice(0, -1))}
                className="rounded-md bg-white/10 px-2 py-1 text-xs hover:bg-white/20"
              >
                − prompt
              </button>
            )}
          </div>
          {error && <p className="text-xs text-red-200">{error}</p>}
          <p className="text-xs opacity-60">
            Saving re-flags the package for render.
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={save}
              disabled={saving}
              className="rounded-md bg-green-500/20 px-3 py-1 text-xs text-green-100 hover:bg-green-500/30 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              onClick={() => setEditing(false)}
              disabled={saving}
              className="rounded-md bg-white/10 px-3 py-1 text-xs hover:bg-white/20 disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function EditablePlatformMetaSection({
  pkg,
  onRefresh,
}: {
  pkg: Package;
  onRefresh: () => Promise<void> | void;
}) {
  return (
    <Section title="Per-platform meta">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {PLATFORMS.map(({ key, label }) => (
          <EditableMetaCard
            key={key}
            pkg={pkg}
            platformKey={key}
            platformLabel={label}
            onRefresh={onRefresh}
          />
        ))}
      </div>
    </Section>
  );
}

function EditableMetaCard({
  pkg,
  platformKey,
  platformLabel,
  onRefresh,
}: {
  pkg: Package;
  platformKey: string;
  platformLabel: string;
  onRefresh: () => Promise<void> | void;
}) {
  const currentTitle = pkg.titles?.[platformKey] ?? "";
  const currentTags = pkg.hashtags?.[platformKey] ?? [];
  const currentTagStr = currentTags.join(" ");

  const [editing, setEditing] = useState(false);
  const [titleDraft, setTitleDraft] = useState(currentTitle);
  const [tagsDraft, setTagsDraft] = useState(currentTagStr);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = () => {
    setTitleDraft(currentTitle);
    setTagsDraft(currentTagStr);
    setError(null);
    setEditing(true);
  };

  const save = async () => {
    const nextTitles = { ...(pkg.titles ?? {}), [platformKey]: titleDraft };
    const nextTags = tagsDraft
      .split(/\s+/)
      .map((t) => t.trim())
      .filter((t) => t.length > 0);
    const nextHashtags = { ...(pkg.hashtags ?? {}), [platformKey]: nextTags };
    setSaving(true);
    setError(null);
    try {
      await patchPackage(pkg.id, {
        titles: nextTitles,
        hashtags: nextHashtags,
      });
      await onRefresh();
      setEditing(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-md border border-white/5 bg-white/5 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-medium">{platformLabel}</h3>
        {!editing && (
          <button
            onClick={startEdit}
            className="rounded-md bg-white/10 px-2 py-1 text-xs hover:bg-white/20"
          >
            Edit
          </button>
        )}
      </div>

      {!editing ? (
        <>
          <div className="mb-3">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-xs opacity-60">Title</span>
              <CopyButton text={currentTitle || "—"} />
            </div>
            <p className="text-sm">{currentTitle || "—"}</p>
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-xs opacity-60">
                Hashtags ({currentTags.length})
              </span>
              <CopyButton text={currentTagStr} />
            </div>
            <p className="text-sm opacity-80">{currentTagStr || "—"}</p>
          </div>
        </>
      ) : (
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs opacity-60">Title</label>
            <input
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              className="w-full rounded-md border border-white/10 bg-black/40 p-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs opacity-60">
              Hashtags (space-separated)
            </label>
            <textarea
              value={tagsDraft}
              onChange={(e) => setTagsDraft(e.target.value)}
              className="h-20 w-full rounded-md border border-white/10 bg-black/40 p-2 font-mono text-xs"
            />
          </div>
          {error && <p className="text-xs text-red-200">{error}</p>}
          <div className="flex items-center gap-2">
            <button
              onClick={save}
              disabled={saving}
              className="rounded-md bg-green-500/20 px-3 py-1 text-xs text-green-100 hover:bg-green-500/30 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              onClick={() => setEditing(false)}
              disabled={saving}
              className="rounded-md bg-white/10 px-3 py-1 text-xs hover:bg-white/20 disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function DossierEditor({
  bookId,
  dossier,
  onSaved,
}: {
  bookId: number;
  dossier: Record<string, unknown> | null;
  onSaved: () => Promise<void> | void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const startEdit = () => {
    setDraft(JSON.stringify(dossier ?? {}, null, 2));
    setParseError(null);
    setSaveError(null);
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setParseError(null);
    setSaveError(null);
  };

  const save = async () => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(draft);
    } catch (e) {
      setParseError(String(e));
      return;
    }
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      setParseError("Dossier must be a JSON object.");
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      await apiFetch(`/books/${bookId}`, {
        method: "PATCH",
        body: JSON.stringify({ dossier: parsed }),
      });
      await onSaved();
      setEditing(false);
    } catch (e) {
      setSaveError(String(e));
    } finally {
      setSaving(false);
    }
  };

  const clear = async () => {
    if (!confirm("Clear the dossier? Next generation will rebuild it.")) return;
    setSaving(true);
    setSaveError(null);
    try {
      await apiFetch(`/books/${bookId}`, {
        method: "PATCH",
        body: JSON.stringify({ dossier: null }),
      });
      await onSaved();
      setEditing(false);
    } catch (e) {
      setSaveError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="mb-6 rounded-lg border border-white/10 p-6">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="font-medium">Book dossier</h2>
          <p className="mt-1 text-xs opacity-60">
            Structured research threaded into every generation. Edit to steer the
            hooks, script, and scene prompts toward specific motifs.
          </p>
        </div>
        {!editing && (
          <div className="flex items-center gap-2">
            <button
              onClick={startEdit}
              className="rounded-md bg-white/10 px-3 py-1.5 text-sm hover:bg-white/20"
            >
              {dossier ? "Edit" : "Write"}
            </button>
            {dossier && (
              <button
                onClick={clear}
                disabled={saving}
                className="rounded-md bg-white/5 px-3 py-1.5 text-sm opacity-70 hover:bg-white/10 hover:opacity-100 disabled:opacity-40"
                title="Clear — next /generate will rebuild via the LLM"
              >
                Clear
              </button>
            )}
          </div>
        )}
      </div>

      {!editing ? (
        dossier ? (
          <pre className="max-h-96 overflow-auto rounded-md bg-black/40 p-3 text-xs leading-relaxed">
            {JSON.stringify(dossier, null, 2)}
          </pre>
        ) : (
          <p className="text-xs italic opacity-60">
            No dossier yet — it will be built on the first /generate call.
          </p>
        )
      ) : (
        <div className="space-y-3">
          <textarea
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              setParseError(null);
            }}
            spellCheck={false}
            className="h-80 w-full rounded-md border border-white/10 bg-black/40 p-3 font-mono text-xs leading-relaxed"
          />
          {parseError && (
            <p className="text-xs text-red-200">{parseError}</p>
          )}
          {saveError && (
            <p className="text-xs text-red-200">Save failed: {saveError}</p>
          )}
          <div className="flex items-center gap-2">
            <button
              onClick={save}
              disabled={saving}
              className="rounded-md bg-green-500/20 px-3 py-1.5 text-sm text-green-100 hover:bg-green-500/30 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              onClick={cancel}
              disabled={saving}
              className="rounded-md bg-white/10 px-3 py-1.5 text-sm hover:bg-white/20 disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
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
