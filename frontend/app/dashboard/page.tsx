"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { apiFetch } from "@/lib/api";

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

const STATUS_STYLES: Record<string, string> = {
  discovered: "bg-slate-500/20 text-slate-200",
  generating: "bg-amber-500/20 text-amber-200",
  review: "bg-blue-500/20 text-blue-200",
  scheduled: "bg-green-500/20 text-green-200",
  published: "bg-emerald-600/30 text-emerald-200",
  skipped: "bg-white/5 text-white/50",
};

const STATUSES = [
  "discovered",
  "generating",
  "review",
  "scheduled",
  "published",
];

export default function DashboardPage() {
  const [books, setBooks] = useState<Book[] | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [showSkipped, setShowSkipped] = useState(false);
  const [search, setSearch] = useState("");
  const [genreFilter, setGenreFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

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
      await apiFetch<{ fetched: number; created: number; skipped: number }>(
        "/discover/run",
        { method: "POST" },
      );
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setDiscovering(false);
    }
  };

  const updateGenre = async (bookId: number, genre: string) => {
    try {
      await apiFetch(`/books/${bookId}`, {
        method: "PATCH",
        body: JSON.stringify({ genre_override: genre || null }),
      });
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

  // Cheap client-side grouping for the "scheduled but skipped" summary line.
  const skippedCount = useMemo(
    () => books?.filter((b) => b.status === "skipped").length ?? 0,
    [books],
  );

  // Client-side filter: search + genre + status. Runs on the already-fetched
  // list — no round-trip. Matches title OR author, case-insensitive.
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
    <main className="mx-auto max-w-6xl p-8">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">Book Queue</h1>
          <p className="text-sm opacity-70">
            Discovered books ranked by score. Click a title to review its
            content package.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs opacity-70 select-none">
            <input
              type="checkbox"
              checked={showSkipped}
              onChange={(e) => setShowSkipped(e.target.checked)}
              className="h-4 w-4"
            />
            Show skipped
          </label>
          <button
            onClick={runDiscovery}
            disabled={discovering}
            className="rounded-md bg-white/10 px-4 py-2 text-sm hover:bg-white/20 disabled:opacity-50"
          >
            {discovering ? "Running…" : "Run NYT Discovery"}
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-6 rounded-md border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      {books && books.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <input
            type="search"
            placeholder="Search title or author…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 min-w-[200px] rounded-md border border-white/10 bg-transparent px-3 py-1.5 text-sm placeholder:opacity-50"
          />
          <select
            value={genreFilter}
            onChange={(e) => setGenreFilter(e.target.value)}
            className="rounded-md border border-white/10 bg-transparent px-2 py-1.5 text-sm"
          >
            <option value="">All genres</option>
            {GENRES.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border border-white/10 bg-transparent px-2 py-1.5 text-sm"
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
            {showSkipped && <option value="skipped">skipped</option>}
          </select>
          {activeFilterCount > 0 && (
            <button
              onClick={() => {
                setSearch("");
                setGenreFilter("");
                setStatusFilter("");
              }}
              className="rounded-md bg-white/10 px-3 py-1.5 text-xs hover:bg-white/20"
            >
              Clear ({activeFilterCount})
            </button>
          )}
          {filtered && (
            <span className="text-xs opacity-60">
              {filtered.length}/{books.length} books
            </span>
          )}
        </div>
      )}

      {books === null ? (
        <div className="rounded-lg border border-white/10 p-6 text-sm opacity-70">
          Loading…
        </div>
      ) : books.length === 0 ? (
        <div className="rounded-lg border border-white/10 p-6 text-sm opacity-70">
          Queue is empty. Click <span className="font-medium">Run NYT Discovery</span>{" "}
          to fetch the current bestseller list.
          {!showSkipped && skippedCount === 0 && (
            <div className="mt-2 text-xs opacity-60">
              (Skipped books hidden by default.)
            </div>
          )}
        </div>
      ) : filtered && filtered.length === 0 ? (
        <div className="rounded-lg border border-white/10 p-6 text-sm opacity-70">
          No books match your filters. Clear or loosen them to see more.
        </div>
      ) : (
        <section className="overflow-x-auto rounded-lg border border-white/10">
          <table className="w-full text-sm">
            <thead className="border-b border-white/10 bg-white/5">
              <tr className="text-left">
                <th className="px-4 py-2 font-medium">Title</th>
                <th className="px-4 py-2 font-medium">Author</th>
                <th className="px-4 py-2 font-medium">Genre</th>
                <th className="px-4 py-2 font-medium">Score</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {(filtered ?? []).map((b) => (
                <tr
                  key={b.id}
                  className={`border-b border-white/5 last:border-0 hover:bg-white/5 ${
                    b.status === "skipped" ? "opacity-60" : ""
                  }`}
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/book/${b.id}`}
                      className="underline-offset-4 hover:underline"
                    >
                      {b.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 opacity-70">{b.author}</td>
                  <td className="px-4 py-3">
                    <GenreSelect book={b} onChange={updateGenre} />
                  </td>
                  <td className="px-4 py-3 tabular-nums">
                    {b.score.toFixed(1)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        STATUS_STYLES[b.status] ?? "bg-white/10"
                      }`}
                    >
                      {b.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => toggleSkip(b)}
                        className="rounded-md bg-white/10 px-2.5 py-1 text-xs hover:bg-white/20"
                        title={
                          b.status === "skipped"
                            ? "Un-skip — put it back in the queue"
                            : "Skip — hide from the queue"
                        }
                      >
                        {b.status === "skipped" ? "Unskip" : "Skip"}
                      </button>
                      <Link
                        href={`/book/${b.id}`}
                        className="rounded-md bg-white/10 px-3 py-1 text-xs hover:bg-white/20"
                      >
                        Open
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}

function GenreSelect({
  book,
  onChange,
}: {
  book: Book;
  onChange: (bookId: number, genre: string) => void;
}) {
  // Empty string = auto (no override). A named genre = override set.
  const value = book.genre_source === "override" ? book.genre ?? "" : "";
  const autoLabel =
    book.genre_source === "auto" && book.genre
      ? `auto (${book.genre})`
      : "auto";

  return (
    <select
      value={value}
      onChange={(e) => onChange(book.id, e.target.value)}
      className="rounded-md border border-white/10 bg-transparent px-2 py-1 text-sm"
    >
      <option value="">{autoLabel}</option>
      {GENRES.map((g) => (
        <option key={g} value={g}>
          {g}
        </option>
      ))}
    </select>
  );
}
