"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ChevronLeft, Play, BookOpen, Package } from "lucide-react";

import { apiFetch, pollJob, type Job, type Series } from "@/lib/api";

const FORMAT_LABELS: Record<string, string> = {
  short_hook: "Short Hook",
  list: "List",
  author_ranking: "Author Ranking",
  series_episode: "Series Episode",
  deep_dive: "Deep Dive",
  recap: "Recap",
  monthly_report: "Monthly Report",
};

export default function SeriesDetailPage() {
  const params = useParams<{ id: string }>();
  const seriesId = Number(params.id);

  const [series, setSeries] = useState<Series | null>(null);
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setError(null);
    try {
      setSeries(await apiFetch<Series>(`/series/${seriesId}`));
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    refresh();
  }, [seriesId]);

  const handleGenerate = async () => {
    setGenerating(true);
    setProgress(null);
    setError(null);
    try {
      const { job_id } = await apiFetch<{ job_id: number }>(
        `/series/${seriesId}/generate?async=true`,
        { method: "POST", body: JSON.stringify({}) },
      );
      await pollJob(job_id, (job: Job) => {
        setProgress(job.message ?? job.status);
      });
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setGenerating(false);
      setProgress(null);
    }
  };

  if (!series) {
    return (
      <div className="mx-auto max-w-6xl p-8">
        {error ? (
          <div className="rounded-lg border border-red-500/20 bg-red-500/[0.06] px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        ) : (
          <div className="flex items-center justify-center py-20 text-slate-500 text-sm">
            Loading...
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl p-8">
      {/* Breadcrumb */}
      <Link
        href="/series"
        className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors mb-6"
      >
        <ChevronLeft className="h-3 w-3" />
        All series
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-white tracking-tight">
            {series.title}
          </h1>
          <div className="flex items-center gap-3 mt-2 text-sm text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500/60" />
              {FORMAT_LABELS[series.format] ?? series.format}
            </span>
            <span className="text-slate-700">/</span>
            <span>{series.series_type.replace(/_/g, " ")}</span>
            <span className="text-slate-700">/</span>
            <span
              className={
                series.status === "active"
                  ? "text-emerald-400"
                  : "text-slate-400"
              }
            >
              {series.status}
            </span>
          </div>
          {series.description && (
            <p className="mt-3 text-sm text-slate-500 max-w-xl leading-relaxed">
              {series.description}
            </p>
          )}
        </div>

        <button
          onClick={handleGenerate}
          disabled={generating || series.books.length === 0}
          className="flex items-center gap-2 rounded-lg bg-amber-500/90 px-4 py-2 text-sm font-medium text-black transition hover:bg-amber-400 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <Play className="h-3.5 w-3.5" />
          {generating ? "Generating..." : "Generate"}
        </button>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/[0.06] px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {progress && (
        <div className="mb-6 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] px-4 py-3 text-sm text-amber-200 animate-pulse">
          {progress}
        </div>
      )}

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Books */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <BookOpen className="h-4 w-4 text-slate-500" />
            <h2 className="text-sm font-medium text-slate-300">
              Books
              <span className="ml-1.5 text-slate-600">
                ({series.books.length})
              </span>
            </h2>
          </div>

          {series.books.length === 0 ? (
            <div className="rounded-lg border border-dashed border-white/[0.08] p-6 text-center">
              <p className="text-sm text-slate-500 mb-1">No books attached</p>
              <p className="text-xs text-slate-600">
                <code className="rounded bg-white/[0.06] px-1.5 py-0.5">
                  POST /series/{seriesId}/books
                </code>
              </p>
            </div>
          ) : (
            <div className="space-y-1.5">
              {series.books.map((b) => (
                <Link
                  key={b.book_id}
                  href={`/book/${b.book_id}`}
                  className="flex items-center gap-3 rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-3 transition hover:bg-white/[0.04] hover:border-white/[0.1]"
                >
                  <span className="flex h-6 w-6 items-center justify-center rounded-md bg-white/[0.06] text-[11px] font-bold text-slate-400 tabular-nums">
                    {b.position}
                  </span>
                  <span className="text-sm text-slate-300">
                    Book #{b.book_id}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </section>

        {/* Packages */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Package className="h-4 w-4 text-slate-500" />
            <h2 className="text-sm font-medium text-slate-300">
              Packages
              <span className="ml-1.5 text-slate-600">
                ({series.packages.length})
              </span>
            </h2>
          </div>

          {series.packages.length === 0 ? (
            <div className="rounded-lg border border-dashed border-white/[0.08] p-6 text-center">
              <p className="text-sm text-slate-500 mb-1">No packages yet</p>
              <p className="text-xs text-slate-600">
                Hit Generate to create one
              </p>
            </div>
          ) : (
            <div className="space-y-1.5">
              {series.packages.map((pkg) => (
                <div
                  key={pkg.id}
                  className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    {pkg.part_number != null && (
                      <span className="rounded-md bg-amber-500/10 px-2 py-[2px] text-[11px] font-medium text-amber-300 ring-1 ring-amber-500/20">
                        Part {pkg.part_number}
                        {series.total_parts
                          ? ` of ${series.total_parts}`
                          : ""}
                      </span>
                    )}
                    <span className="text-sm text-slate-300">
                      Package #{pkg.id}
                    </span>
                    <span className="text-xs text-slate-600">{pkg.format}</span>
                  </div>
                  <span
                    className={`rounded-full px-2 py-[2px] text-[11px] font-medium ${
                      pkg.is_approved
                        ? "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/20"
                        : "bg-white/[0.04] text-slate-500 ring-1 ring-white/[0.06]"
                    }`}
                  >
                    {pkg.is_approved ? "Approved" : "Pending"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
