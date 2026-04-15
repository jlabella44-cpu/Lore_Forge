const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
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
  return `${BASE_URL}/renders/${packageId}/${filename}`;
}

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
