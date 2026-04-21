"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Check, Copy, Play } from "lucide-react";

import { apiFetch, dollars, pollJob, rendersUrl, type CostSummary } from "@/lib/api";
import { ContentCover } from "@/components/ui/ContentCover";
import { Button } from "@/components/ui/Button";
import { Card, HeroCard } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { Crumb } from "@/components/ui/Crumb";
import { ScoreBar } from "@/components/ui/ScoreBar";
import { StatusChip } from "@/components/ui/StatusChip";
import { Tabs } from "@/components/ui/Tabs";

type HookAlternative = { angle: string; text: string };

type Scene = {
  section?: string;
  label?: string;
  prompt?: string;
  prompts?: string[];
  focus: string;
};

function scenePrompts(scene: Scene): string[] {
  if (scene.prompts && scene.prompts.length > 0) return scene.prompts;
  if (scene.prompt) return [scene.prompt];
  return [];
}

type CaptionWord = { word: string; start: number; end: number };

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
  rendered_at: string | null;
  rendered_duration_seconds: number | null;
  rendered_size_bytes: number | null;
  needs_rerender: boolean;
};

type BookDetail = {
  id: number;
  title: string;
  subtitle: string;
  isbn: string | null;
  genre: string | null;
  genre_override: string | null;
  cover_url: string | null;
  status: string;
  score: number;
  dossier: Record<string, unknown> | null;
  packages: Package[];
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

const PUBLISH_TARGETS = [
  { key: "yt_shorts", glyph: "YT", label: "YouTube Shorts" },
  { key: "tiktok", glyph: "TT", label: "TikTok" },
  { key: "ig_reels", glyph: "IG", label: "Instagram Reels" },
  { key: "threads", glyph: "TH", label: "Threads" },
];

const PLATFORMS = [
  { key: "tiktok", glyph: "TT", label: "TikTok" },
  { key: "yt_shorts", glyph: "YT", label: "YouTube Shorts" },
  { key: "ig_reels", glyph: "IG", label: "Instagram Reels" },
  { key: "threads", glyph: "TH", label: "Threads" },
];

type TabKey = "script" | "hooks" | "scenes" | "narration" | "meta";

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

// Static export can't pre-render `/book/[id]`, so the detail page is
// reached as `/item?id=123` and the ID is read from the query string.
// `useSearchParams()` triggers Next's CSR bailout during prerender, which
// requires a Suspense boundary at the module's default export.
export default function BookReviewPage() {
  return (
    <Suspense fallback={null}>
      <BookReviewContent />
    </Suspense>
  );
}

function BookReviewContent() {
  const searchParams = useSearchParams();
  const itemId = searchParams.get("id") ?? "";
  const [book, setBook] = useState<BookDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("script");
  const [costs, setCosts] = useState<CostSummary | null>(null);
  const [regenNote, setRegenNote] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generateStage, setGenerateStage] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [renderStage, setRenderStage] = useState<string | null>(null);
  const [publishing, setPublishing] = useState<string | null>(null);
  const [published, setPublished] = useState<
    Record<string, { external_id: string; published_at: string } | { error: string }>
  >({});

  const refresh = async () => {
    setError(null);
    try {
      const data = await apiFetch<BookDetail>(`/items/${itemId}`);
      setBook(data);
      setActiveId((prev) => prev ?? data.packages[0]?.id ?? null);
    } catch (e) {
      setError(String(e));
    }
    apiFetch<CostSummary>("/analytics/cost?days=365").then(setCosts).catch(() => {});
  };

  useEffect(() => {
    if (!itemId) return;
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemId]);

  // Preserve tab in URL hash.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const hash = window.location.hash.replace("#", "") as TabKey;
    if (["script", "hooks", "scenes", "narration", "meta"].includes(hash)) {
      setActiveTab(hash);
    }
  }, []);
  useEffect(() => {
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", `#${activeTab}`);
    }
  }, [activeTab]);

  const generatePackage = async (note?: string) => {
    setGenerating(true);
    setGenerateStage("queued");
    setError(null);
    try {
      const queued = await apiFetch<{ job_id: number; status: string }>(
        `/items/${itemId}/generate?async=true`,
        { method: "POST", body: JSON.stringify({ note: note ?? null }) },
      );
      const job = await pollJob(queued.job_id, (j) =>
        setGenerateStage(j.message ?? j.status),
      );
      if (job.status === "failed") throw new Error(job.error ?? "Generation failed");
      const result = job.result as { package_id: number };
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

  const render = async (packageId: number) => {
    setRendering(true);
    setRenderStage("queued");
    setError(null);
    try {
      const queued = await apiFetch<{ job_id: number; status: string }>(
        `/packages/${packageId}/render?async=true`,
        { method: "POST" },
      );
      const job = await pollJob(queued.job_id, (j) =>
        setRenderStage(j.message ?? j.status),
      );
      if (job.status === "failed") throw new Error(job.error ?? "Render failed");
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setRendering(false);
      setRenderStage(null);
    }
  };

  const publish = async (packageId: number, platform: string) => {
    setPublishing(platform);
    setError(null);
    try {
      const res = await apiFetch<{
        external_id: string;
        published_at: string;
      }>(`/publish/${packageId}/${platform}`, { method: "POST" });
      setPublished((prev) => ({ ...prev, [platform]: res }));
      await refresh();
    } catch (e) {
      setPublished((prev) => ({ ...prev, [platform]: { error: String(e) } }));
    } finally {
      setPublishing(null);
    }
  };

  if (!book) {
    return (
      <div className="mx-auto max-w-[1240px] px-10 pb-20 pt-9">
        <Crumb href="/dashboard" label="Queue" />
        <p className="mt-6 text-sm text-fg-3">
          {error ? `Error: ${error}` : "Loading…"}
        </p>
      </div>
    );
  }

  const effectiveGenre =
    book.genre_override || book.genre || "uncategorized";
  const active =
    book.packages.find((p) => p.id === activeId) ?? book.packages[0] ?? null;
  const costCents =
    costs?.per_package.find((p) => p.package_id === active?.id)?.cents ?? null;

  return (
    <div className="mx-auto max-w-[1240px] px-10 pb-20 pt-9">
      <Crumb href="/dashboard" label="Queue" />

      {/* Hero */}
      <HeroCard className="mb-7">
        <div className="grid grid-cols-[140px_1fr_auto] items-start gap-6">
          <div className="w-[140px]">
            <ContentCover
              coverUrl={book.cover_url}
              title={book.title}
              subtitle={book.subtitle}
            />
          </div>
          <div>
            <span className="mb-2 block font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
              {effectiveGenre}
            </span>
            <h1 className="font-serif text-[40px] font-[450] leading-[1.05] tracking-[-0.02em] text-fg-0">
              {book.title}
            </h1>
            <p className="mt-2 text-sm text-fg-2">by {book.subtitle}</p>
            <div className="mt-4 flex items-center gap-3">
              <StatusChip status={book.status} />
              <ScoreBar score={book.score} width={72} />
              {costCents !== null && costCents > 0 && (
                <Chip variant="plain" dot={false}>
                  {dollars(costCents)} spent
                </Chip>
              )}
            </div>
          </div>
          <HeroActions
            pkg={active}
            onApprove={approve}
            approving={approving}
            onRender={render}
            rendering={rendering}
            renderStage={renderStage}
          />
        </div>
      </HeroCard>

      {error && (
        <div className="mb-6 rounded-lg border border-err/30 bg-err-soft p-4 text-sm text-[oklch(90%_0.12_25)]">
          {error}
        </div>
      )}

      <DossierEditor
        itemId={book.id}
        dossier={book.dossier}
        onSaved={refresh}
      />

      {book.packages.length === 0 ? (
        <Card className="text-center text-sm text-fg-2">
          <p className="mb-4">No content package yet.</p>
          <Button variant="primary" onClick={() => generatePackage()} disabled={generating}>
            {generating ? "Generating…" : "Generate Package"}
          </Button>
        </Card>
      ) : (
        active && (
          <>
          <RenderStatus pkg={active} />
          <div className="grid grid-cols-1 gap-8 @max-[1100px]:grid-cols-1 lg:grid-cols-[1fr_320px]">
            <div className="min-w-0">
              <Tabs
                tabs={[
                  { key: "script", label: "Script" },
                  {
                    key: "hooks",
                    label: "Hooks",
                    count: active.hook_alternatives?.length,
                  },
                  {
                    key: "scenes",
                    label: "Image Prompts",
                    count: (active.visual_prompts ?? []).reduce(
                      (n, s) => n + scenePrompts(s).length,
                      0,
                    ),
                  },
                  { key: "narration", label: "Narration" },
                  { key: "meta", label: "Platform Meta" },
                ]}
                active={activeTab}
                onChange={setActiveTab}
              />

              {activeTab === "script" && (
                <EditableScript pkg={active} onRefresh={refresh} />
              )}
              {activeTab === "hooks" && (
                <HookPortfolio pkg={active} onRefresh={refresh} />
              )}
              {activeTab === "scenes" && (
                <EditableScenes pkg={active} onRefresh={refresh} />
              )}
              {activeTab === "narration" && <NarrationView pkg={active} />}
              {activeTab === "meta" && (
                <EditablePlatformMeta pkg={active} onRefresh={refresh} />
              )}

              <RegenerateForm
                note={regenNote}
                setNote={setRegenNote}
                onSubmit={() => generatePackage(regenNote || undefined)}
                generating={generating}
                generateStage={generateStage}
              />
            </div>

            <aside className="lg:sticky lg:top-6 lg:h-fit">
              <PublishPanel
                pkg={active}
                onPublish={publish}
                publishing={publishing}
                published={published}
              />
              <RevisionHistory
                packages={book.packages}
                activeId={active.id}
                onSelect={setActiveId}
              />
            </aside>
          </div>
          </>
        )
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hero actions
// ---------------------------------------------------------------------------

function HeroActions({
  pkg,
  onApprove,
  approving,
  onRender,
  rendering,
  renderStage,
}: {
  pkg: Package | null;
  onApprove: (id: number) => void;
  approving: boolean;
  onRender: (id: number) => void;
  rendering: boolean;
  renderStage: string | null;
}) {
  if (!pkg) return null;
  return (
    <div className="flex flex-col items-end gap-2">
      {pkg.is_approved ? (
        <Button
          variant="primary"
          onClick={() => onRender(pkg.id)}
          disabled={rendering}
          title="Synthesize narration, generate images, render mp4"
        >
          {rendering ? `Rendering… ${renderStage ?? ""}`.trim() : "Render Video"}
        </Button>
      ) : (
        <Button
          variant="ok"
          onClick={() => onApprove(pkg.id)}
          disabled={approving}
        >
          {approving ? "Approving…" : "Approve"}
        </Button>
      )}
      {pkg.needs_rerender && pkg.is_approved && (
        <span className="font-mono text-[10.5px] uppercase tracking-[0.1em] text-[oklch(82%_0.15_85)]">
          needs re-render
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Render status — banner when re-render needed, subtle line when fresh
// ---------------------------------------------------------------------------

function RenderStatus({ pkg }: { pkg: Package }) {
  if (!pkg.rendered_at) return null;

  if (pkg.needs_rerender) {
    return (
      <div className="mb-6 rounded-lg border border-[oklch(82%_0.15_85/0.3)] bg-[oklch(82%_0.15_85/0.08)] p-4 text-sm text-[oklch(90%_0.13_85)]">
        Needs re-render — narration has changed since the last render
      </div>
    );
  }

  const parts: string[] = [];
  if (pkg.rendered_duration_seconds != null) {
    parts.push(formatDuration(pkg.rendered_duration_seconds));
  }
  if (pkg.rendered_size_bytes != null) {
    parts.push(formatBytes(pkg.rendered_size_bytes));
  }
  parts.push(`rendered ${formatTimeAgo(pkg.rendered_at)}`);

  return (
    <p className="mb-6 font-mono text-[11px] text-fg-3">
      {parts.join(" · ")}
    </p>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const rem = Math.round(seconds - m * 60);
  return rem === 0 ? `${m}m` : `${m}m ${rem}s`;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function formatTimeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diffMs / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

// ---------------------------------------------------------------------------
// Script tab — editable
// ---------------------------------------------------------------------------

async function patchPackage(id: number, body: Record<string, unknown>) {
  await apiFetch(`/packages/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

function EditableScript({
  pkg,
  onRefresh,
}: {
  pkg: Package;
  onRefresh: () => void | Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const startEdit = () => {
    setDraft(pkg.script);
    setErr(null);
    setEditing(true);
  };

  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      await patchPackage(pkg.id, { script: draft });
      await onRefresh();
      setEditing(false);
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  };

  const wordCount = pkg.narration?.split(/\s+/).filter(Boolean).length ?? 0;

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
            90-second script
          </div>
          <div className="mt-1 font-mono text-[11px] text-fg-3">
            {wordCount} narration words
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!editing && <CopyBtn text={pkg.script} />}
          {!editing && (
            <Button size="sm" onClick={startEdit}>
              Edit
            </Button>
          )}
        </div>
      </div>

      {!editing ? (
        <p className="whitespace-pre-wrap font-serif text-base leading-[1.65] text-fg-1">
          {pkg.script}
        </p>
      ) : (
        <div className="space-y-3">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            spellCheck={false}
            className="h-96 w-full rounded-md border border-hair bg-ink-0 p-3 font-mono text-xs leading-relaxed focus:border-[oklch(72%_0.14_285/0.5)] focus:outline-none"
          />
          {err && <p className="text-xs text-[oklch(90%_0.12_25)]">{err}</p>}
          <p className="text-xs text-fg-3">
            Script must contain all five section headers. Saving flags the
            package for re-render.
          </p>
          <div className="flex gap-2">
            <Button variant="ok" size="sm" onClick={save} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Hook portfolio with radio + Apply to script
// ---------------------------------------------------------------------------

function HookPortfolio({
  pkg,
  onRefresh,
}: {
  pkg: Package;
  onRefresh: () => void | Promise<void>;
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
      await apiFetch(`/packages/${pkg.id}/apply-chosen-hook`, { method: "POST" });
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
  const hookInSync =
    !!chosenText &&
    !!pkg.script &&
    pkg.script
      .replace(/^#+\s*HOOK\s*:?\s*\n?/i, "")
      .trimStart()
      .startsWith(chosenText.trim());

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <p className="flex-1 text-xs text-fg-3">
          Click an alternative to make it the chosen hook. Swapping only
          updates metadata — use &ldquo;Apply to script&rdquo; to deterministically
          rewrite the script&apos;s HOOK line with the chosen hook.
        </p>
        <Button
          size="sm"
          onClick={applyToScript}
          disabled={applying || hookInSync || pendingIndex !== null}
          title={
            hookInSync
              ? "Script's HOOK already matches the chosen alternative"
              : "Rewrite script HOOK + narration opening"
          }
        >
          {applying ? "Applying…" : "Apply to script"}
        </Button>
      </div>
      {applyError && (
        <p className="text-xs text-[oklch(90%_0.12_25)]">Apply failed: {applyError}</p>
      )}

      {(pkg.hook_alternatives ?? []).map((h, i) => {
        const isChosen = i === pkg.chosen_hook_index;
        const isPending = pendingIndex === i;
        return (
          <button
            key={i}
            onClick={() => choose(i)}
            disabled={pendingIndex !== null}
            className={`w-full rounded-md border p-4 text-left transition-all ${
              isChosen
                ? "border-[oklch(72%_0.14_285/0.45)] bg-accent-soft shadow-[0_0_0_1px_oklch(72%_0.14_285/0.15),_0_0_20px_oklch(72%_0.14_285/0.1)]"
                : "border-hair bg-white/[0.015] hover:border-hair-strong hover:bg-white/[0.025]"
            }`}
          >
            <div className="mb-2 flex items-center gap-2">
              <Chip variant={isChosen ? "accent" : "plain"} dot={false}>
                {ANGLE_LABEL[h.angle] ?? h.angle}
              </Chip>
              {isChosen && <Chip variant="accent">Chosen</Chip>}
              {isPending && (
                <span className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-fg-3">
                  saving…
                </span>
              )}
            </div>
            <p className="font-serif text-[18px] leading-[1.35] tracking-[-0.005em] text-fg-0">
              {h.text}
            </p>
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Image prompts — editable per scene
// ---------------------------------------------------------------------------

function EditableScenes({
  pkg,
  onRefresh,
}: {
  pkg: Package;
  onRefresh: () => void | Promise<void>;
}) {
  const scenes = pkg.visual_prompts ?? [];
  return (
    <div className="space-y-3">
      {scenes.map((_, i) => (
        <EditableSceneRow
          key={i}
          pkg={pkg}
          sceneIndex={i}
          onRefresh={onRefresh}
        />
      ))}
    </div>
  );
}

function EditableSceneRow({
  pkg,
  sceneIndex,
  onRefresh,
}: {
  pkg: Package;
  sceneIndex: number;
  onRefresh: () => void | Promise<void>;
}) {
  const scene = (pkg.visual_prompts ?? [])[sceneIndex];
  const prompts = scenePrompts(scene);
  const sectionKey = scene.section ?? scene.label ?? "";
  const label = SECTION_LABEL[sectionKey] ?? sectionKey;

  const [editing, setEditing] = useState(false);
  const [drafts, setDrafts] = useState<string[]>(prompts);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const startEdit = () => {
    setDrafts(prompts);
    setErr(null);
    setEditing(true);
  };

  const save = async () => {
    const cleaned = drafts.map((p) => p.trim()).filter((p) => p.length > 0);
    if (cleaned.length === 0) {
      setErr("At least one prompt is required.");
      return;
    }
    const allScenes = (pkg.visual_prompts ?? []).map((s, i) =>
      i === sceneIndex ? { ...s, prompts: cleaned, prompt: undefined } : s,
    );
    setSaving(true);
    setErr(null);
    try {
      await patchPackage(pkg.id, { visual_prompts: allScenes });
      await onRefresh();
      setEditing(false);
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Chip variant="plain" dot={false}>
            {label}
          </Chip>
          {prompts.length > 1 && (
            <Chip variant="ember" dot={false}>
              {prompts.length} images
            </Chip>
          )}
          {scene.focus && (
            <span className="text-xs text-fg-3">{scene.focus}</span>
          )}
        </div>
        {!editing && (
          <Button size="sm" onClick={startEdit}>
            Edit
          </Button>
        )}
      </div>

      {!editing ? (
        <div className="grid grid-cols-[88px_1fr] gap-4">
          <SceneThumb sectionLabel={label} index={sceneIndex + 1} />
          <div className="space-y-2">
            {prompts.map((prompt, j) => (
              <div key={j} className="flex items-start justify-between gap-3 text-sm text-fg-1">
                <div className="flex-1 border-l border-hair pl-3 leading-relaxed">
                  {prompts.length > 1 && (
                    <span className="mr-2 font-mono text-[10px] text-fg-4">
                      #{j + 1}
                    </span>
                  )}
                  {prompt}
                </div>
                <CopyBtn text={prompt} />
              </div>
            ))}
          </div>
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
              className="h-20 w-full rounded-md border border-hair bg-ink-0 p-2 font-mono text-xs leading-relaxed focus:border-[oklch(72%_0.14_285/0.5)] focus:outline-none"
            />
          ))}
          <div className="flex items-center gap-2">
            <Button size="sm" variant="ghost" onClick={() => setDrafts((ds) => [...ds, ""])}>
              + prompt
            </Button>
            {drafts.length > 1 && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setDrafts((ds) => ds.slice(0, -1))}
              >
                − prompt
              </Button>
            )}
          </div>
          {err && <p className="text-xs text-[oklch(90%_0.12_25)]">{err}</p>}
          <div className="flex gap-2">
            <Button variant="ok" size="sm" onClick={save} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

function SceneThumb({ sectionLabel, index }: { sectionLabel: string; index: number }) {
  return (
    <div
      className="relative grid aspect-[9/16] place-items-center overflow-hidden rounded-[4px]"
      style={{
        background:
          "linear-gradient(135deg, oklch(25% 0.04 280), oklch(18% 0.02 260))",
      }}
    >
      <div
        className="absolute inset-0"
        style={{
          background:
            "repeating-linear-gradient(45deg, transparent 0, transparent 8px, oklch(100% 0 0 / 0.02) 8px, oklch(100% 0 0 / 0.02) 9px)",
        }}
      />
      <span className="relative font-mono text-[9.5px] uppercase tracking-[0.14em] text-fg-3">
        {sectionLabel} · {index}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Narration (read-only, with captions preview)
// ---------------------------------------------------------------------------

function NarrationView({ pkg }: { pkg: Package }) {
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
          TTS-ready narration
        </div>
        <CopyBtn text={pkg.narration} />
      </div>
      <p className="whitespace-pre-wrap font-serif text-[17px] leading-[1.55] text-fg-1">
        {pkg.narration}
      </p>
      {pkg.captions && pkg.captions.length > 0 && (
        <CaptionsPreview captions={pkg.captions} />
      )}
    </Card>
  );
}

function CaptionsPreview({ captions }: { captions: CaptionWord[] }) {
  const [expanded, setExpanded] = useState(false);
  const duration = captions[captions.length - 1]?.end ?? 0;
  const preview = captions.slice(0, 14).map((c) => c.word).join(" ");
  return (
    <div className="mt-4 rounded-md border border-hair bg-white/[0.02] p-3 text-xs">
      <div className="mb-2 flex items-center justify-between">
        <div className="font-mono text-fg-3">
          {captions.length} words · {duration.toFixed(1)}s
        </div>
        <Button size="sm" variant="ghost" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "Collapse" : "Show all"}
        </Button>
      </div>
      {expanded ? (
        <ol className="max-h-64 space-y-0.5 overflow-y-auto font-mono text-[11px] text-fg-2">
          {captions.map((c, i) => (
            <li key={i}>
              <span className="mr-2 inline-block w-16 text-fg-4 tabular-nums">
                {c.start.toFixed(2)}s
              </span>
              {c.word}
            </li>
          ))}
        </ol>
      ) : (
        <p className="italic text-fg-3">
          {preview}
          {captions.length > 14 ? "…" : ""}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Platform meta — editable per card
// ---------------------------------------------------------------------------

function EditablePlatformMeta({
  pkg,
  onRefresh,
}: {
  pkg: Package;
  onRefresh: () => void | Promise<void>;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {PLATFORMS.map(({ key, glyph, label }) => (
        <EditableMetaCard
          key={key}
          pkg={pkg}
          platformKey={key}
          platformLabel={label}
          glyph={glyph}
          onRefresh={onRefresh}
        />
      ))}
    </div>
  );
}

function EditableMetaCard({
  pkg,
  platformKey,
  platformLabel,
  glyph,
  onRefresh,
}: {
  pkg: Package;
  platformKey: string;
  platformLabel: string;
  glyph: string;
  onRefresh: () => void | Promise<void>;
}) {
  const currentTitle = pkg.titles?.[platformKey] ?? "";
  const currentTags = pkg.hashtags?.[platformKey] ?? [];
  const currentTagStr = currentTags.join(" ");

  const [editing, setEditing] = useState(false);
  const [titleDraft, setTitleDraft] = useState(currentTitle);
  const [tagsDraft, setTagsDraft] = useState(currentTagStr);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const startEdit = () => {
    setTitleDraft(currentTitle);
    setTagsDraft(currentTagStr);
    setErr(null);
    setEditing(true);
  };

  const save = async () => {
    const nextTags = tagsDraft.split(/\s+/).map((t) => t.trim()).filter(Boolean);
    setSaving(true);
    setErr(null);
    try {
      await patchPackage(pkg.id, {
        titles: { ...(pkg.titles ?? {}), [platformKey]: titleDraft },
        hashtags: { ...(pkg.hashtags ?? {}), [platformKey]: nextTags },
      });
      await onRefresh();
      setEditing(false);
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <PlatformGlyph glyph={glyph} />
          <h4 className="font-mono text-xs uppercase tracking-[0.1em] text-fg-2">
            {platformLabel}
          </h4>
        </div>
        {!editing && (
          <Button size="sm" onClick={startEdit}>
            Edit
          </Button>
        )}
      </div>

      {!editing ? (
        <>
          <div className="mb-3">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-[10.5px] text-fg-3">Title</span>
              <CopyBtn text={currentTitle} />
            </div>
            <p className="text-sm text-fg-1">{currentTitle || "—"}</p>
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-[10.5px] text-fg-3">
                Hashtags ({currentTags.length})
              </span>
              <CopyBtn text={currentTagStr} />
            </div>
            <div className="flex flex-wrap gap-1.5">
              {currentTags.length === 0 ? (
                <span className="text-sm text-fg-3">—</span>
              ) : (
                currentTags.map((t, i) => (
                  <span key={i} className="font-mono text-[11px] text-fg-2">
                    {t}
                  </span>
                ))
              )}
            </div>
          </div>
        </>
      ) : (
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-[10.5px] text-fg-3">Title</label>
            <input
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              className="w-full rounded-md border border-hair bg-ink-0 p-2 text-sm focus:border-[oklch(72%_0.14_285/0.5)] focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-[10.5px] text-fg-3">
              Hashtags (space-separated)
            </label>
            <textarea
              value={tagsDraft}
              onChange={(e) => setTagsDraft(e.target.value)}
              className="h-20 w-full rounded-md border border-hair bg-ink-0 p-2 font-mono text-xs focus:border-[oklch(72%_0.14_285/0.5)] focus:outline-none"
            />
          </div>
          {err && <p className="text-xs text-[oklch(90%_0.12_25)]">{err}</p>}
          <div className="flex gap-2">
            <Button variant="ok" size="sm" onClick={save} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

function PlatformGlyph({ glyph }: { glyph: string }) {
  return (
    <div className="grid h-[22px] w-[22px] place-items-center rounded-[5px] bg-white/[0.06] font-mono text-[10px] font-semibold tracking-[0.02em] text-fg-2">
      {glyph}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Publish panel (right rail)
// ---------------------------------------------------------------------------

type PublishStatus =
  | { external_id: string; published_at: string }
  | { error: string };

function PublishPanel({
  pkg,
  onPublish,
  publishing,
  published,
}: {
  pkg: Package;
  onPublish: (id: number, platform: string) => void;
  publishing: string | null;
  published: Record<string, PublishStatus>;
}) {
  return (
    <Card className="mb-4 p-0">
      <div className="p-4">
        {/* Video frame placeholder */}
        <div
          className="relative mb-4 flex aspect-[9/16] items-center justify-center overflow-hidden rounded-md"
          style={{
            background:
              "linear-gradient(180deg, oklch(15% 0.02 260), oklch(8% 0.01 260))",
            boxShadow: "inset 0 0 0 1px var(--hair)",
          }}
        >
          {pkg.is_approved ? (
            <video
              key={pkg.id}
              src={rendersUrl(pkg.id)}
              controls
              playsInline
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex flex-col items-center gap-2 text-fg-3">
              <Play className="h-6 w-6 opacity-60" />
              <span className="font-mono text-[10.5px] uppercase tracking-[0.14em]">
                not rendered
              </span>
            </div>
          )}
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "repeating-linear-gradient(0deg, transparent 0, transparent 3px, oklch(100% 0 0 / 0.02) 3px, oklch(100% 0 0 / 0.02) 4px)",
            }}
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          {PUBLISH_TARGETS.map(({ key, glyph, label }) => {
            const status = published[key];
            const isPublishing = publishing === key;
            const done = status && !("error" in status);
            return (
              <button
                key={key}
                onClick={() => onPublish(pkg.id, key)}
                disabled={isPublishing || !!done || !pkg.is_approved}
                className={`flex items-center justify-between gap-2 rounded-md border px-3 py-2.5 text-[13px] transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                  done
                    ? "border-[oklch(78%_0.13_155/0.25)] bg-ok-soft text-[oklch(92%_0.1_155)]"
                    : "border-hair bg-white/[0.02] text-fg-1 hover:border-hair-strong hover:bg-white/[0.04]"
                }`}
              >
                <span className="flex items-center gap-2.5">
                  <PlatformGlyph glyph={glyph} />
                  <span className="truncate">{label}</span>
                </span>
                {done ? (
                  <Check className="h-3.5 w-3.5" />
                ) : isPublishing ? (
                  <span className="font-mono text-[10px] text-fg-3">…</span>
                ) : null}
              </button>
            );
          })}
        </div>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Revision history (right rail)
// ---------------------------------------------------------------------------

function RevisionHistory({
  packages,
  activeId,
  onSelect,
}: {
  packages: Package[];
  activeId: number;
  onSelect: (id: number) => void;
}) {
  return (
    <div>
      <div className="mb-3 font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
        Revision history
      </div>
      <div className="space-y-2">
        {packages.map((p) => {
          const active = p.id === activeId;
          return (
            <button
              key={p.id}
              onClick={() => onSelect(p.id)}
              className={`block w-full rounded-md border p-3 text-left transition-all ${
                active
                  ? "border-[oklch(72%_0.14_285/0.35)] bg-accent-soft"
                  : "border-hair bg-white/[0.02] hover:border-hair-strong hover:bg-white/[0.04]"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-fg-2">
                  Rev {p.revision_number}
                </span>
                {p.is_approved && <Chip variant="ok">Approved</Chip>}
              </div>
              {p.regenerate_note && (
                <div className="mt-1 line-clamp-2 text-xs italic text-fg-3">
                  “{p.regenerate_note}”
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Regenerate form
// ---------------------------------------------------------------------------

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
    <Card className="mt-6">
      <h3 className="mb-3">Regenerate</h3>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder='Optional: tell Claude how to change it. "Make the hook darker."'
        className="mb-3 h-24 w-full rounded-md border border-hair bg-transparent p-3 text-sm focus:border-[oklch(72%_0.14_285/0.5)] focus:outline-none"
      />
      <div className="flex items-center gap-3">
        <Button variant="primary" onClick={onSubmit} disabled={generating}>
          {generating ? "Generating…" : note ? "Regenerate with note" : "Regenerate"}
        </Button>
        {generating && generateStage && (
          <span className="font-mono text-[11px] text-fg-3">
            {generateStage}
          </span>
        )}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Dossier editor (JSON, preserved from PR #8)
// ---------------------------------------------------------------------------

function DossierEditor({
  itemId,
  dossier,
  onSaved,
}: {
  itemId: number;
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
      await apiFetch(`/items/${itemId}`, {
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
      await apiFetch(`/items/${itemId}`, {
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
    <Card className="mb-6">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
            Book dossier
          </div>
          <p className="mt-1 text-xs text-fg-3">
            Structured research threaded into every generation.
          </p>
        </div>
        {!editing && (
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={startEdit}>
              {dossier ? "Edit" : "Write"}
            </Button>
            {dossier && (
              <Button
                size="sm"
                variant="ghost"
                onClick={clear}
                disabled={saving}
                title="Clear — next /generate rebuilds via the LLM"
              >
                Clear
              </Button>
            )}
          </div>
        )}
      </div>

      {!editing ? (
        dossier ? (
          <pre className="max-h-96 overflow-auto rounded-md bg-ink-0 p-3 font-mono text-xs leading-relaxed text-fg-1">
            {JSON.stringify(dossier, null, 2)}
          </pre>
        ) : (
          <p className="text-xs italic text-fg-3">
            No dossier yet — it&apos;ll be built on the first /generate call.
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
            className="h-80 w-full rounded-md border border-hair bg-ink-0 p-3 font-mono text-xs leading-relaxed focus:border-[oklch(72%_0.14_285/0.5)] focus:outline-none"
          />
          {parseError && <p className="text-xs text-[oklch(90%_0.12_25)]">{parseError}</p>}
          {saveError && (
            <p className="text-xs text-[oklch(90%_0.12_25)]">Save failed: {saveError}</p>
          )}
          <div className="flex gap-2">
            <Button variant="ok" size="sm" onClick={save} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Copy button
// ---------------------------------------------------------------------------

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const onClick = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard may be blocked */
    }
  };
  return (
    <button
      onClick={onClick}
      className="grid h-[26px] w-[26px] place-items-center rounded-md border border-hair text-fg-3 transition-colors hover:border-hair-strong hover:text-fg-1"
      title="Copy"
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}
