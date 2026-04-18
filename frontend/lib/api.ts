// Base URL resolution priority:
//   1. `window.__LORE_FORGE_API__` — injected by the Tauri shell at app
//      boot with the sidecar's loopback port (unknown until runtime).
//   2. `NEXT_PUBLIC_API_URL` — dev fallback baked in at build time.
//   3. `http://localhost:8000` — sensible default when neither is set.
// `window` is undefined during the static export build, so the guard is
// required to keep `npm run build` green.
declare global {
  interface Window {
    __LORE_FORGE_API__?: string;
  }
}

function baseUrl(): string {
  if (typeof window !== "undefined" && window.__LORE_FORGE_API__) {
    return window.__LORE_FORGE_API__;
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${baseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

/** URL to an asset inside the backend's /renders static mount. */
export function rendersUrl(packageId: number, filename = "out.mp4"): string {
  return `${baseUrl()}/renders/${packageId}/${filename}`;
}

export type CostSummary = {
  total_cents: number;
  total_usd: string;
  by_call_name: Record<string, { count: number; cents: number }>;
  by_provider: Record<string, number>;
  per_package: Array<{
    package_id: number;
    book_id: number;
    book_title: string;
    revision_number: number;
    cents: number;
  }>;
  since: string;
  days: number;
  record_count: number;
  budget: {
    daily_cents: number | null;
    today_cents: number;
    remaining_cents: number | null;
  };
};

/** Format a cents value as "$X.XX". */
export function dollars(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

// ---------------------------------------------------------------------------
// Series
// ---------------------------------------------------------------------------

export type SeriesBook = {
  book_id: number;
  position: number;
};

export type SeriesPackage = {
  id: number;
  part_number: number | null;
  format: string;
  is_approved: boolean;
};

export type Series = {
  id: number;
  slug: string;
  title: string;
  description: string | null;
  format: string;
  series_type: string;
  source_book_id: number | null;
  source_author: string | null;
  total_parts: number | null;
  status: string;
  created_at: string | null;
  books: SeriesBook[];
  packages: SeriesPackage[];
};

export type Job = {
  id: number;
  kind: string;
  target_id: number;
  status: "queued" | "running" | "succeeded" | "failed";
  message: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
};

/**
 * Poll GET /jobs/{id} every `intervalMs` until it reaches a terminal state.
 * Calls `onProgress` with each intermediate snapshot so the UI can show
 * the `message` field live.
 */
export async function pollJob(
  jobId: number,
  onProgress: (job: Job) => void,
  intervalMs = 1200,
): Promise<Job> {
  while (true) {
    const job = await apiFetch<Job>(`/jobs/${jobId}`);
    onProgress(job);
    if (job.status === "succeeded" || job.status === "failed") {
      return job;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}
