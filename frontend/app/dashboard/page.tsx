"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Search, LayoutGrid, List, X } from "lucide-react";

import { apiFetch, pollJob } from "@/lib/api";
import { BookCover } from "@/components/ui/BookCover";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { PageHead } from "@/components/ui/PageHead";
import { ScoreBar } from "@/components/ui/ScoreBar";
import { StatusChip } from "@/components/ui/StatusChip";

type Book = {
  id: number;
  title: string;
  author: string;
  cover_url: string | null;
  genre: string | null;
  genre_source: "override" | "auto";
  genre_confidence: number | null;
  score: number;
  status: string;
};

const GENRES = [
  "fantasy",
  "scifi",
  "romance",
  "thriller",
  "historical_fiction",
  "other",
];

const STATUSES = [
  "discovered",
  "generating",
  "review",
  "scheduled",
  "rendered",
  "published",
];

type View = "list" | "grid";
const VIEW_KEY = "lore-forge:dashboard-view";

export default function DashboardPage() {
  const [books, setBooks] = useState<Book[] | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [showSkipped, setShowSkipped] = useState(false);
  const [search, setSearch] = useState("");
  const [genreFilter, setGenreFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("list");
  const [batch, setBatch] = useState<{
    total: number;
    done: number;
    failed: number;
  } | null>(null);

  useEffect(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem(VIEW_KEY) : null;
    if (saved === "grid" || saved === "list") setView(saved);
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") localStorage.setItem(VIEW_KEY, view);
  }, [view]);

  const refresh = async (includeSkipped = showSkipped) => {
    setError(null);
    try {
      const query = includeSkipped ? "?include_skipped=true" : "";
      setBooks(await apiFetch<Book[]>(`/books${query}`));
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    refresh(showSkipped);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showSkipped]);

  const runDiscovery = async () => {
    setDiscovering(true);
    setError(null);
    try {
      await apiFetch("/discover/run", { method: "POST" });
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setDiscovering(false);
    }
  };

  const runBatchGenerate = async () => {
    setError(null);
    setBatch(null);
    try {
      const res = await apiFetch<{
        enqueued: number;
        eligible_count: number;
        job_ids: number[];
      }>("/books/generate-all", { method: "POST" });

      if (res.enqueued === 0) {
        setError("No eligible books — every discovered book already has a package.");
        return;
      }
      setBatch({ total: res.enqueued, done: 0, failed: 0 });

      await Promise.all(
        res.job_ids.map(async (jobId) => {
          try {
            const final = await pollJob(jobId, () => {});
            setBatch((prev) => {
              if (!prev) return prev;
              const next = { ...prev, done: prev.done + 1 };
              if (final.status === "failed") next.failed += 1;
              return next;
            });
          } catch {
            setBatch((prev) =>
              prev ? { ...prev, done: prev.done + 1, failed: prev.failed + 1 } : prev,
            );
          }
        }),
      );
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  };

  const toggleSkip = async (book: Book) => {
    const action = book.status === "skipped" ? "unskip" : "skip";
    try {
      await apiFetch(`/books/${book.id}/${action}`, { method: "POST" });
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  };

  const filtered = useMemo(() => {
    if (!books) return null;
    const q = search.trim().toLowerCase();
    return books.filter((b) => {
      if (q && !b.title.toLowerCase().includes(q) && !b.author.toLowerCase().includes(q)) {
        return false;
      }
      if (genreFilter && (b.genre ?? "") !== genreFilter) return false;
      if (statusFilter && b.status !== statusFilter) return false;
      return true;
    });
  }, [books, search, genreFilter, statusFilter]);

  const activeFilterCount =
    (search ? 1 : 0) + (genreFilter ? 1 : 0) + (statusFilter ? 1 : 0);

  return (
    <div className="mx-auto max-w-[1240px] px-10 pb-20 pt-9">
      <PageHead
        eyebrow="Pipeline · 01"
        title="Book Queue"
        lede="Books ranked by score across your enabled sources. Click a title to review its content package."
        actions={
          <>
            <label className="flex cursor-pointer select-none items-center gap-2 text-xs text-fg-2">
              <input
                type="checkbox"
                checked={showSkipped}
                onChange={(e) => setShowSkipped(e.target.checked)}
                className="h-3.5 w-3.5"
                style={{ accentColor: "var(--accent)" }}
              />
              Show skipped
            </label>
            <Button
              onClick={runBatchGenerate}
              disabled={batch !== null && batch.done < batch.total}
              title="Generate packages for every discovered book without one."
            >
              {batch && batch.done < batch.total
                ? `Generating ${batch.done}/${batch.total}…`
                : "Generate All"}
            </Button>
            <Button
              variant="primary"
              onClick={runDiscovery}
              disabled={discovering}
              title="Fan out across every source in SOURCES_ENABLED."
            >
              {discovering ? "Running…" : "Run Discovery"}
            </Button>
          </>
        }
      />

      {batch && <BatchProgress batch={batch} />}

      {error && (
        <div className="mb-6 rounded-lg border border-err/30 bg-err-soft p-4 text-sm text-[oklch(90%_0.12_25)]">
          {error}
        </div>
      )}

      <Filters
        search={search}
        setSearch={setSearch}
        genre={genreFilter}
        setGenre={setGenreFilter}
        status={statusFilter}
        setStatus={setStatusFilter}
        view={view}
        setView={setView}
        activeFilterCount={activeFilterCount}
        total={books?.length ?? 0}
        shown={filtered?.length ?? 0}
        onClearFilters={() => {
          setSearch("");
          setGenreFilter("");
          setStatusFilter("");
        }}
        showSkipped={showSkipped}
      />

      {books === null ? (
        <EmptyState>Loading…</EmptyState>
      ) : books.length === 0 ? (
        <EmptyState>
          Queue is empty. Click <span className="text-fg-0">Run Discovery</span> to fetch the current bestseller list.
        </EmptyState>
      ) : filtered && filtered.length === 0 ? (
        <EmptyState>No books match your filters.</EmptyState>
      ) : view === "list" ? (
        <BookTable books={filtered ?? []} onToggleSkip={toggleSkip} />
      ) : (
        <BookGrid books={filtered ?? []} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function Filters({
  search,
  setSearch,
  genre,
  setGenre,
  status,
  setStatus,
  view,
  setView,
  activeFilterCount,
  total,
  shown,
  onClearFilters,
  showSkipped,
}: {
  search: string;
  setSearch: (v: string) => void;
  genre: string;
  setGenre: (v: string) => void;
  status: string;
  setStatus: (v: string) => void;
  view: View;
  setView: (v: View) => void;
  activeFilterCount: number;
  total: number;
  shown: number;
  onClearFilters: () => void;
  showSkipped: boolean;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <div className="relative min-w-[260px] flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-3" />
        <input
          type="search"
          placeholder="Search title or author…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-9 w-full rounded-md border border-hair bg-white/[0.02] pl-9 pr-3 text-sm text-fg-1 placeholder:text-fg-3 focus:border-[oklch(72%_0.14_285/0.5)] focus:bg-white/[0.04] focus:outline-none"
        />
      </div>
      <SelectCustom value={genre} onChange={setGenre}>
        <option value="">All genres</option>
        {GENRES.map((g) => (
          <option key={g} value={g}>
            {g}
          </option>
        ))}
      </SelectCustom>
      <SelectCustom value={status} onChange={setStatus}>
        <option value="">All statuses</option>
        {STATUSES.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
        {showSkipped && <option value="skipped">skipped</option>}
      </SelectCustom>
      {activeFilterCount > 0 && (
        <Button variant="ghost" size="sm" onClick={onClearFilters}>
          <X className="h-3 w-3" /> Clear ({activeFilterCount})
        </Button>
      )}
      <span className="mx-2 font-mono text-[11px] text-fg-3">
        {shown}/{total}
      </span>
      <ViewToggle view={view} setView={setView} />
    </div>
  );
}

function SelectCustom({
  value,
  onChange,
  children,
}: {
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-9 rounded-md border border-hair bg-white/[0.02] px-3 text-sm text-fg-1 focus:border-[oklch(72%_0.14_285/0.5)] focus:outline-none"
    >
      {children}
    </select>
  );
}

function ViewToggle({ view, setView }: { view: View; setView: (v: View) => void }) {
  return (
    <div className="ml-auto inline-flex items-center gap-0.5 rounded-md border border-hair bg-white/[0.03] p-0.5">
      <button
        onClick={() => setView("list")}
        className={`flex items-center gap-1.5 rounded-[4px] px-2.5 py-1 text-xs ${
          view === "list" ? "bg-white/[0.08] text-fg-0" : "text-fg-2 hover:text-fg-1"
        }`}
        title="List view"
      >
        <List className="h-3.5 w-3.5" /> List
      </button>
      <button
        onClick={() => setView("grid")}
        className={`flex items-center gap-1.5 rounded-[4px] px-2.5 py-1 text-xs ${
          view === "grid" ? "bg-white/[0.08] text-fg-0" : "text-fg-2 hover:text-fg-1"
        }`}
        title="Grid view"
      >
        <LayoutGrid className="h-3.5 w-3.5" /> Grid
      </button>
    </div>
  );
}

function BookTable({
  books,
  onToggleSkip,
}: {
  books: Book[];
  onToggleSkip: (book: Book) => void;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-hair bg-white/[0.015]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-hair text-left">
            <th className="w-[56px] px-4 py-3" />
            <HeaderCell>Title</HeaderCell>
            <HeaderCell>Author</HeaderCell>
            <HeaderCell>Genre</HeaderCell>
            <HeaderCell>Score</HeaderCell>
            <HeaderCell>Status</HeaderCell>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          {books.map((b) => (
            <tr
              key={b.id}
              className={`border-b border-hair last:border-0 hover:bg-white/[0.025] ${
                b.status === "skipped" ? "opacity-45" : ""
              }`}
            >
              <td className="py-3 pl-4 pr-0">
                <div className="h-10 w-7">
                  <BookCover
                    coverUrl={b.cover_url}
                    title={b.title}
                    author={b.author}
                  />
                </div>
              </td>
              <td className="px-4 py-3">
                <Link
                  href={`/book/${b.id}`}
                  className="text-fg-0 transition-colors hover:text-accent"
                >
                  {b.title}
                </Link>
              </td>
              <td className="px-4 py-3 text-fg-2">{b.author}</td>
              <td className="px-4 py-3">
                {b.genre && <Chip variant="plain">{b.genre}</Chip>}
              </td>
              <td className="px-4 py-3">
                <ScoreBar score={b.score} />
              </td>
              <td className="px-4 py-3">
                <StatusChip status={b.status} />
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center justify-end gap-1.5">
                  <Button variant="ghost" size="sm" onClick={() => onToggleSkip(b)}>
                    {b.status === "skipped" ? "Unskip" : "Skip"}
                  </Button>
                  <Link
                    href={`/book/${b.id}`}
                    className="rounded-md bg-white/[0.03] px-2.5 py-[5px] text-xs font-medium text-fg-1 transition-colors hover:border-hair-strong hover:bg-white/[0.07]"
                  >
                    Open
                  </Link>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HeaderCell({ children }: { children: React.ReactNode }) {
  return (
    <th className="px-4 py-3 font-mono text-[10.5px] font-normal uppercase tracking-[0.12em] text-fg-3">
      {children}
    </th>
  );
}

function BookGrid({ books }: { books: Book[] }) {
  return (
    <div
      className="grid gap-x-5 gap-y-6"
      style={{ gridTemplateColumns: "repeat(auto-fill, minmax(168px, 1fr))" }}
    >
      {books.map((b) => (
        <Link key={b.id} href={`/book/${b.id}`} className="group block">
          <div className="mb-2.5 overflow-hidden rounded-md border border-hair transition-transform duration-200 group-hover:-translate-y-[3px] group-hover:shadow-[0_6px_30px_rgba(0,0,0,0.4)]">
            <BookCover coverUrl={b.cover_url} title={b.title} author={b.author} />
          </div>
          <div className="line-clamp-2 text-sm text-fg-1 group-hover:text-fg-0">
            {b.title}
          </div>
          <div className="mt-0.5 truncate text-xs text-fg-3">{b.author}</div>
          <div className="mt-1.5 flex items-center justify-between">
            <StatusChip status={b.status} />
            <span className="font-mono text-[11px] text-fg-3">
              {b.score.toFixed(1)}
            </span>
          </div>
        </Link>
      ))}
    </div>
  );
}

function BatchProgress({
  batch,
}: {
  batch: { total: number; done: number; failed: number };
}) {
  const running = batch.done < batch.total;
  const anyFailed = batch.failed > 0;
  const tone = running ? "warn" : anyFailed ? "err" : "ok";
  const toneBg =
    tone === "warn" ? "bg-warn-soft border-warn/30 text-[oklch(92%_0.1_85)]"
    : tone === "err" ? "bg-err-soft border-err/30 text-[oklch(90%_0.12_25)]"
    : "bg-ok-soft border-ok/30 text-[oklch(92%_0.1_155)]";
  return (
    <div className={`mb-6 rounded-lg border p-3 text-sm ${toneBg}`}>
      <div className="mb-1 flex items-center justify-between">
        <span>
          {running
            ? "Batch generate in progress"
            : anyFailed
              ? `Batch complete with ${batch.failed} failure${batch.failed === 1 ? "" : "s"}`
              : `Batch complete — all ${batch.total} packages generated`}
        </span>
        <span className="font-mono text-xs tabular-nums">
          {batch.done}/{batch.total}
        </span>
      </div>
      <div className="h-[3px] w-full overflow-hidden rounded-[2px] bg-white/[0.06]">
        <div
          className="h-full bg-current transition-all"
          style={{ width: `${(batch.done / batch.total) * 100}%` }}
        />
      </div>
    </div>
  );
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-hair bg-white/[0.015] p-8 text-center text-sm text-fg-2">
      {children}
    </div>
  );
}
