"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ChevronRight, Plus } from "lucide-react";

import { apiFetch, type Series } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Chip, type ChipVariant } from "@/components/ui/Chip";
import { PageHead } from "@/components/ui/PageHead";

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

export default function SeriesListPage() {
  const [seriesList, setSeriesList] = useState<Series[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Series[]>("/series")
      .then(setSeriesList)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="mx-auto max-w-[1240px] px-10 pb-20 pt-9">
      <PageHead
        eyebrow="Pipeline · 02"
        title="Series"
        lede="Group books into themed rankings, deep-dives, and multi-part arcs. Generate all parts together."
        actions={
          <Button variant="primary" disabled title="Creating series from the UI lands later — use POST /series for now">
            <Plus className="h-3.5 w-3.5" /> New series
          </Button>
        }
      />

      {error && (
        <div className="mb-6 rounded-lg border border-err/30 bg-err-soft p-4 text-sm text-[oklch(90%_0.12_25)]">
          {error}
        </div>
      )}

      {seriesList === null ? (
        <Card className="text-center text-sm text-fg-3">Loading…</Card>
      ) : seriesList.length === 0 ? (
        <Card className="text-center text-sm text-fg-2">
          <p className="mb-2">No series yet.</p>
          <p className="text-xs text-fg-3">
            Create one via <code className="rounded bg-white/[0.05] px-1.5 py-0.5 font-mono text-[11px]">POST /series</code>
          </p>
        </Card>
      ) : (
        <div className="grid gap-3">
          {seriesList.map((s) => {
            const variant = STATUS_VARIANT[s.status] ?? "plain";
            return (
              <Link key={s.id} href={`/series/view?id=${s.id}`} className="block">
                <Card className="cursor-pointer transition-colors hover:border-hair-strong hover:bg-white/[0.04]">
                  <div className="grid grid-cols-[1fr_auto] items-center gap-5">
                    <div>
                      <div className="mb-2 flex items-center gap-2.5">
                        <h2 className="font-serif text-[19px] font-[450] tracking-[-0.005em] text-fg-0">
                          {s.title}
                        </h2>
                        <Chip variant={variant}>{s.status}</Chip>
                      </div>
                      {s.description && (
                        <p className="mb-3 max-w-[640px] text-[13.5px] leading-[1.5] text-fg-2">
                          {s.description}
                        </p>
                      )}
                      <div className="flex items-center gap-4 font-mono text-xs tracking-[0.04em] text-fg-3">
                        <span className="flex items-center gap-1.5">
                          <span className="inline-block h-[5px] w-[5px] rounded-full bg-accent" />
                          {FORMAT_LABELS[s.format] ?? s.format}
                        </span>
                        <span>
                          {s.books.length} book{s.books.length !== 1 ? "s" : ""}
                        </span>
                        <span>
                          {s.packages.length} package
                          {s.packages.length !== 1 ? "s" : ""}
                        </span>
                        {s.total_parts ? <span>{s.total_parts} parts</span> : null}
                      </div>
                    </div>
                    <ChevronRight className="h-4 w-4 text-fg-3" />
                  </div>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
