"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { apiFetch, type Series } from "@/lib/api";

const FORMAT_LABELS: Record<string, string> = {
  short_hook: "Short Hook",
  list: "List",
  author_ranking: "Author Ranking",
  series_episode: "Series Episode",
  deep_dive: "Deep Dive",
  recap: "Recap",
  monthly_report: "Monthly Report",
};

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-500/20 text-green-200",
  complete: "bg-blue-500/20 text-blue-200",
  paused: "bg-slate-500/20 text-slate-200",
};

export default function SeriesListPage() {
  const [seriesList, setSeriesList] = useState<Series[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setError(null);
    try {
      setSeriesList(await apiFetch<Series[]>("/series"));
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Series</h1>
        <Link
          href="/dashboard"
          className="text-sm text-slate-400 hover:text-white transition"
        >
          &larr; Dashboard
        </Link>
      </div>

      {error && (
        <p className="mb-4 rounded bg-red-900/40 px-3 py-2 text-red-200 text-sm">
          {error}
        </p>
      )}

      {seriesList === null ? (
        <p className="text-slate-400">Loading…</p>
      ) : seriesList.length === 0 ? (
        <p className="text-slate-400">
          No series yet. Create one via the API:{" "}
          <code className="text-xs bg-slate-800 px-1 rounded">
            POST /series
          </code>
        </p>
      ) : (
        <div className="space-y-3">
          {seriesList.map((s) => (
            <Link
              key={s.id}
              href={`/series/${s.id}`}
              className="block rounded-lg border border-slate-700 bg-slate-800/60 p-4 hover:border-slate-500 transition"
            >
              <div className="flex items-center gap-3 mb-1">
                <h2 className="text-lg font-semibold text-white">
                  {s.title}
                </h2>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    STATUS_STYLES[s.status] ?? STATUS_STYLES.active
                  }`}
                >
                  {s.status}
                </span>
              </div>

              <div className="flex gap-4 text-sm text-slate-400">
                <span>{FORMAT_LABELS[s.format] ?? s.format}</span>
                <span>{s.books.length} book{s.books.length !== 1 ? "s" : ""}</span>
                <span>
                  {s.packages.length} package
                  {s.packages.length !== 1 ? "s" : ""}
                </span>
              </div>

              {s.description && (
                <p className="mt-2 text-sm text-slate-500 line-clamp-2">
                  {s.description}
                </p>
              )}
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
