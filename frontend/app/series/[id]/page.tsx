"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Play } from "lucide-react";

import { apiFetch, pollJob, type Job, type Series } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, HeroCard } from "@/components/ui/Card";
import { Chip, type ChipVariant } from "@/components/ui/Chip";
import { Crumb } from "@/components/ui/Crumb";

const FORMAT_LABELS: Record<string, string> = {
  short_hook: "Short Hook",
  list: "List",
  author_ranking: "Author Ranking",
  series_episode: "Series Episode",
  deep_dive: "Deep Dive",
  recap: "Recap",
  monthly_report: "Monthly Report",
};

const STATUS_VARIANT: Record<string, ChipVariant> = {
  active: "ok",
  complete: "info",
  paused: "plain",
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      await pollJob(job_id, (job: Job) => setProgress(job.message ?? job.status));
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
      <div className="mx-auto max-w-[1240px] px-10 pb-20 pt-9">
        <Crumb href="/series" label="All series" />
        <Card className="text-sm text-fg-3">
          {error ? `Error: ${error}` : "Loading…"}
        </Card>
      </div>
    );
  }

  const statusVariant = STATUS_VARIANT[series.status] ?? "plain";

  return (
    <div className="mx-auto max-w-[1240px] px-10 pb-20 pt-9">
      <Crumb href="/series" label="All series" />

      <HeroCard className="mb-7">
        <div className="grid grid-cols-[1fr_auto] items-center gap-6">
          <div>
            <span className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
              {FORMAT_LABELS[series.format] ?? series.format} ·{" "}
              {series.series_type.replace(/_/g, " ")}
            </span>
            <h1 className="mt-2.5 font-serif text-[34px] font-[450] leading-[1.1] tracking-[-0.02em] text-fg-0">
              {series.title}
            </h1>
            {series.description && (
              <p className="mt-2.5 max-w-[720px] text-sm leading-[1.55] text-fg-2">
                {series.description}
              </p>
            )}
            <div className="mt-3.5 flex items-center gap-2.5">
              <Chip variant={statusVariant}>{series.status}</Chip>
              {series.total_parts && (
                <Chip variant="plain" dot={false}>
                  {series.packages.length} of {series.total_parts} parts
                </Chip>
              )}
            </div>
          </div>
          <Button
            variant="primary"
            onClick={handleGenerate}
            disabled={generating || series.books.length === 0}
          >
            <Play className="h-3.5 w-3.5" />
            {generating ? "Generating…" : "Generate all parts"}
          </Button>
        </div>
      </HeroCard>

      {error && (
        <div className="mb-6 rounded-lg border border-err/30 bg-err-soft p-4 text-sm text-[oklch(90%_0.12_25)]">
          {error}
        </div>
      )}

      {progress && (
        <div className="mb-6 rounded-lg border border-warn/30 bg-warn-soft p-3 text-sm text-[oklch(92%_0.1_85)]">
          {progress}
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <section>
          <SectionHead title="Books" count={series.books.length} />
          {series.books.length === 0 ? (
            <Card className="text-center text-sm text-fg-3">
              <p className="mb-1">No books attached.</p>
              <p className="font-mono text-[11px]">
                POST /series/{seriesId}/books
              </p>
            </Card>
          ) : (
            <div className="grid gap-2">
              {series.books.map((b, i) => (
                <a
                  key={b.book_id}
                  href={`/book/${b.book_id}`}
                  className="flex items-center gap-3.5 rounded-md border border-hair bg-white/[0.02] p-3 transition-colors hover:border-hair-strong hover:bg-white/[0.04]"
                >
                  <span className="grid h-7 w-7 place-items-center rounded-[5px] bg-white/[0.04] font-mono text-[11px] text-fg-2">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="text-[13.5px] text-fg-1">
                    Book #{b.book_id}
                  </span>
                  <span className="ml-auto font-mono text-[11px] text-fg-4">
                    pos {b.position}
                  </span>
                </a>
              ))}
            </div>
          )}
        </section>

        <section>
          <SectionHead title="Parts" count={series.packages.length} />
          {series.packages.length === 0 ? (
            <Card className="text-center">
              <div className="text-fg-3">No parts generated yet</div>
              <div className="mt-1 text-xs text-fg-4">
                Hit Generate to create the first one
              </div>
            </Card>
          ) : (
            <div className="grid gap-2">
              {series.packages.map((pkg) => (
                <div
                  key={pkg.id}
                  className="flex items-center gap-3 rounded-md border border-hair bg-white/[0.02] p-3"
                >
                  {pkg.part_number != null && (
                    <Chip variant="ember" dot={false}>
                      Part {pkg.part_number}
                      {series.total_parts ? ` of ${series.total_parts}` : ""}
                    </Chip>
                  )}
                  <span className="text-[13px] text-fg-1">
                    Package #{pkg.id}
                  </span>
                  <span className="font-mono text-[11px] text-fg-4">
                    {FORMAT_LABELS[pkg.format] ?? pkg.format}
                  </span>
                  <div className="flex-1" />
                  <Chip variant={pkg.is_approved ? "ok" : "plain"}>
                    {pkg.is_approved ? "Approved" : "Pending"}
                  </Chip>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function SectionHead({ title, count }: { title: string; count: number }) {
  return (
    <div className="mb-3 flex items-center gap-2.5">
      <span className="inline-block h-2 w-2 rounded-full bg-accent" />
      <h2 className="font-serif text-[17px] font-[450] text-fg-0">{title}</h2>
      <span className="font-mono text-[11px] text-fg-3">({count})</span>
    </div>
  );
}
