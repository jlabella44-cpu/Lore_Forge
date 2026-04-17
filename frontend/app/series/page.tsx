"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Layers } from "lucide-react";

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
  active: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/20",
  complete: "bg-blue-500/15 text-blue-300 ring-1 ring-blue-500/20",
  paused: "bg-slate-500/15 text-slate-400 ring-1 ring-slate-500/20",
};

export default function SeriesListPage() {
  const [seriesList, setSeriesList] = useState<Series[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Series[]>("/series")
      .then(setSeriesList)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="mx-auto max-w-6xl p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-white tracking-tight">
            Series
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Group books into themed lists, rankings, and multi-part series
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/[0.06] px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {seriesList === null ? (
        <div className="flex items-center justify-center py-20 text-slate-500 text-sm">
          Loading...
        </div>
      ) : seriesList.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="mb-4 rounded-xl bg-white/[0.03] p-4">
            <Layers className="h-8 w-8 text-slate-600" />
          </div>
          <p className="text-sm text-slate-400 mb-1">No series yet</p>
          <p className="text-xs text-slate-600">
            Create one via{" "}
            <code className="rounded bg-white/[0.06] px-1.5 py-0.5 text-slate-400">
              POST /series
            </code>
          </p>
        </div>
      ) : (
        <div className="grid gap-3">
          {seriesList.map((s) => (
            <Link
              key={s.id}
              href={`/series/${s.id}`}
              className="group rounded-lg border border-white/[0.06] bg-white/[0.02] p-5 transition hover:bg-white/[0.04] hover:border-white/[0.1]"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2.5 mb-1.5">
                    <h2 className="text-[15px] font-medium text-white truncate group-hover:text-amber-200 transition-colors">
                      {s.title}
                    </h2>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-[2px] text-[11px] font-medium ${
                        STATUS_STYLES[s.status] ?? STATUS_STYLES.active
                      }`}
                    >
                      {s.status}
                    </span>
                  </div>

                  {s.description && (
                    <p className="text-sm text-slate-500 line-clamp-1 mb-3">
                      {s.description}
                    </p>
                  )}

                  <div className="flex items-center gap-4 text-xs text-slate-500">
                    <span className="flex items-center gap-1.5">
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500/60" />
                      {FORMAT_LABELS[s.format] ?? s.format}
                    </span>
                    <span>
                      {s.books.length} book{s.books.length !== 1 && "s"}
                    </span>
                    <span>
                      {s.packages.length} package
                      {s.packages.length !== 1 && "s"}
                    </span>
                  </div>
                </div>

                <svg
                  className="mt-1 h-4 w-4 text-slate-600 transition-transform group-hover:translate-x-0.5 group-hover:text-slate-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
