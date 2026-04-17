"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { apiFetch, pollJob, type Job, type Series } from "@/lib/api";

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
      <main className="mx-auto max-w-4xl px-4 py-8">
        {error ? (
          <p className="text-red-300">{error}</p>
        ) : (
          <p className="text-slate-400">Loading…</p>
        )}
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-1">
        <Link
          href="/series"
          className="text-sm text-slate-400 hover:text-white transition"
        >
          &larr; Series
        </Link>
      </div>

      <div className="flex items-center justify-between mt-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">{series.title}</h1>
          <p className="text-sm text-slate-400 mt-1">
            {series.format} &middot; {series.series_type} &middot;{" "}
            {series.status}
          </p>
          {series.description && (
            <p className="text-sm text-slate-500 mt-2">{series.description}</p>
          )}
        </div>

        <button
          onClick={handleGenerate}
          disabled={generating || series.books.length === 0}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {generating ? "Generating…" : "Generate"}
        </button>
      </div>

      {error && (
        <p className="mb-4 rounded bg-red-900/40 px-3 py-2 text-red-200 text-sm">
          {error}
        </p>
      )}

      {progress && (
        <p className="mb-4 rounded bg-indigo-900/30 px-3 py-2 text-indigo-200 text-sm">
          {progress}
        </p>
      )}

      {/* Books */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold text-white mb-3">
          Books ({series.books.length})
        </h2>
        {series.books.length === 0 ? (
          <p className="text-sm text-slate-500">
            No books attached. Use{" "}
            <code className="text-xs bg-slate-800 px-1 rounded">
              POST /series/{seriesId}/books
            </code>{" "}
            to add books.
          </p>
        ) : (
          <div className="space-y-2">
            {series.books.map((b) => (
              <div
                key={b.book_id}
                className="flex items-center gap-3 rounded border border-slate-700 bg-slate-800/40 px-3 py-2"
              >
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-700 text-xs font-bold text-slate-300">
                  {b.position}
                </span>
                <Link
                  href={`/book/${b.book_id}`}
                  className="text-sm text-slate-200 hover:text-white transition"
                >
                  Book #{b.book_id}
                </Link>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Packages */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-3">
          Packages ({series.packages.length})
        </h2>
        {series.packages.length === 0 ? (
          <p className="text-sm text-slate-500">
            No packages yet. Hit Generate to create one.
          </p>
        ) : (
          <div className="space-y-2">
            {series.packages.map((pkg) => (
              <div
                key={pkg.id}
                className="flex items-center justify-between rounded border border-slate-700 bg-slate-800/40 px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  {pkg.part_number && (
                    <span className="rounded-full bg-indigo-600/30 px-2 py-0.5 text-xs font-medium text-indigo-200">
                      Part {pkg.part_number}
                      {series.total_parts
                        ? ` of ${series.total_parts}`
                        : ""}
                    </span>
                  )}
                  <span className="text-sm text-slate-300">
                    Package #{pkg.id}
                  </span>
                  <span className="text-xs text-slate-500">{pkg.format}</span>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    pkg.is_approved
                      ? "bg-green-500/20 text-green-200"
                      : "bg-slate-600/30 text-slate-400"
                  }`}
                >
                  {pkg.is_approved ? "Approved" : "Pending"}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
