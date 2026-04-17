"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { History as HistoryIcon } from "lucide-react";

import { apiFetch, rendersUrl, type HistoryRow } from "@/lib/api";

const STATUS_STYLES: Record<string, string> = {
  rendered: "bg-teal-500/20 text-teal-200",
  scheduled: "bg-green-500/20 text-green-200",
  published: "bg-emerald-600/30 text-emerald-200",
  review: "bg-blue-500/20 text-blue-200",
};

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function formatSize(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

function formatRelative(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const diffSec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}

export default function HistoryPage() {
  const [rows, setRows] = useState<HistoryRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    apiFetch<HistoryRow[]>("/books/history")
      .then(setRows)
      .catch((e) => setError(String(e)));
  }, []);

  const filtered = useMemo(() => {
    if (!rows) return null;
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (r) =>
        r.title.toLowerCase().includes(q) ||
        r.author.toLowerCase().includes(q),
    );
  }, [rows, search]);

  const staleCount = useMemo(
    () => rows?.filter((r) => r.needs_rerender).length ?? 0,
    [rows],
  );

  return (
    <div className="mx-auto max-w-6xl p-8">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <HistoryIcon className="h-5 w-5 text-amber-400" />
            <h1 className="text-2xl font-semibold text-white tracking-tight">
              Render History
            </h1>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Books that have been rendered at least once, most-recent first.
            Re-opening these is cheap — cached image prompts don&apos;t re-hit
            the provider.
          </p>
        </div>
        {rows && rows.length > 0 && (
          <div className="text-right text-xs text-slate-500">
            <div>
              <span className="tabular-nums text-slate-300">{rows.length}</span>{" "}
              rendered
            </div>
            {staleCount > 0 && (
              <div className="text-amber-300/80">
                {staleCount} need re-render
              </div>
            )}
          </div>
        )}
      </header>

      {error && (
        <div className="mb-6 rounded-md border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      {rows && rows.length > 0 && (
        <div className="mb-4">
          <input
            type="search"
            placeholder="Search title or author…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-white/10 bg-transparent px-3 py-1.5 text-sm placeholder:opacity-50"
          />
        </div>
      )}

      {rows === null ? (
        <div className="rounded-lg border border-white/10 p-6 text-sm opacity-70">
          Loading…
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-white/10 p-8 text-center text-sm text-slate-400">
          No renders yet. Approve and render a package from the{" "}
          <Link href="/dashboard" className="underline hover:text-slate-200">
            Books queue
          </Link>{" "}
          to start building your history.
        </div>
      ) : filtered && filtered.length === 0 ? (
        <div className="rounded-lg border border-white/10 p-6 text-sm opacity-70">
          No matches.
        </div>
      ) : (
        <section className="overflow-x-auto rounded-lg border border-white/10">
          <table className="w-full text-sm">
            <thead className="border-b border-white/10 bg-white/5">
              <tr className="text-left">
                <th className="px-4 py-2 font-medium">Title</th>
                <th className="px-4 py-2 font-medium">Author</th>
                <th className="px-4 py-2 font-medium">Rendered</th>
                <th className="px-4 py-2 font-medium">Duration</th>
                <th className="px-4 py-2 font-medium">Size</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {(filtered ?? []).map((r) => (
                <tr
                  key={r.book_id}
                  className="border-b border-white/5 last:border-0 hover:bg-white/5"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/book/${r.book_id}`}
                      className="underline-offset-4 hover:underline"
                    >
                      {r.title}
                    </Link>
                    {r.revision_number > 1 && (
                      <span className="ml-2 text-xs opacity-50">
                        rev {r.revision_number}
                      </span>
                    )}
                    {r.needs_rerender && (
                      <span
                        className="ml-2 rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] text-amber-200"
                        title="Narration was edited after this render — the mp4 is stale."
                      >
                        stale
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 opacity-70">{r.author}</td>
                  <td
                    className="px-4 py-3 tabular-nums opacity-80"
                    title={r.rendered_at ?? ""}
                  >
                    {formatRelative(r.rendered_at)}
                  </td>
                  <td className="px-4 py-3 tabular-nums opacity-80">
                    {formatDuration(r.rendered_duration_seconds)}
                  </td>
                  <td className="px-4 py-3 tabular-nums opacity-80">
                    {formatSize(r.rendered_size_bytes)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        STATUS_STYLES[r.status] ?? "bg-white/10"
                      }`}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <a
                        href={rendersUrl(r.latest_package_id)}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-md bg-white/10 px-2.5 py-1 text-xs hover:bg-white/20"
                      >
                        Video
                      </a>
                      <Link
                        href={`/book/${r.book_id}`}
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
    </div>
  );
}
