/**
 * Full-flow happy path: dashboard → book detail → render → publish.
 *
 * Every backend call is intercepted with page.route(). No uvicorn / DB /
 * LLM provider is required. We're testing that the UI correctly consumes
 * what the real backend would send, which is exactly the wire contract
 * pytest's test_generate / test_jobs / test_publish already exercise from
 * the other side.
 */
import { test, expect, type Page, type Route } from "@playwright/test";

const API = "http://localhost:8000";

type Json = Record<string, unknown>;

function jsonRoute(body: Json, status = 200) {
  return (route: Route) =>
    route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

// ---------------------------------------------------------------------------
// canned payloads matching the real backend response shapes
// ---------------------------------------------------------------------------

const BOOKS_LIST = [
  {
    id: 1,
    title: "The Invisible Life of Addie LaRue",
    author: "V. E. Schwab",
    cover_url: null,
    genre: "fantasy",
    genre_source: "auto",
    genre_confidence: 0.93,
    score: 2.0,
    status: "scheduled",
  },
];

const HOOK_ALTERNATIVES = [
  { angle: "curiosity", text: "What would you do if everyone forgot you the second you turned your back?" },
  { angle: "fear", text: "One deal with the devil. Three hundred years of being invisible." },
  { angle: "promise", text: "If you loved The Night Circus, Addie LaRue will haunt your TBR." },
];

const PACKAGE = {
  id: 1,
  revision_number: 1,
  script: "## HOOK\nOne deal with the devil.\n\n## WORLD TEASE\n1714.\n\n## EMOTIONAL PULL\nForgotten.\n\n## SOCIAL PROOF\n#1 NYT.\n\n## CTA\nLink in bio.",
  narration: "One deal with the devil. [PAUSE] Three hundred years of being invisible.",
  hook_alternatives: HOOK_ALTERNATIVES,
  chosen_hook_index: 1,
  visual_prompts: [
    { section: "hook", prompt: "A candle in a mirror", focus: "devil's bargain" },
    { section: "world_tease", prompt: "A French village at dusk", focus: "1714" },
    { section: "emotional_pull", prompt: "Rain-slicked window", focus: "forgotten" },
    { section: "social_proof", prompt: "A stack of books", focus: "bestseller" },
    { section: "cta", prompt: "A leather-bound book", focus: "warm CTA" },
  ],
  section_word_counts: { hook: 6, world_tease: 5, emotional_pull: 3, social_proof: 2, cta: 4 },
  captions: [
    { word: "One", start: 0.1, end: 0.4 },
    { word: "deal", start: 0.45, end: 0.75 },
    { word: "with", start: 0.8, end: 0.95 },
    { word: "the", start: 1.0, end: 1.1 },
    { word: "devil.", start: 1.15, end: 1.8 },
  ],
  titles: {
    tiktok: "She traded her soul for freedom.",
    yt_shorts: "300 years invisible.",
    ig_reels: "Fantasy TBR must-read.",
    threads: "Just finished Addie LaRue and I need to talk.",
  },
  hashtags: {
    tiktok: ["#booktok", "#fantasybooktok"],
    yt_shorts: ["#shorts", "#booktok"],
    ig_reels: ["#bookstagram"],
    threads: ["#books"],
  },
  affiliate_amazon: null,
  affiliate_bookshop: null,
  regenerate_note: null,
  is_approved: true,
  created_at: "2026-04-14T12:00:00",
};

const BOOK_DETAIL = {
  id: 1,
  title: "The Invisible Life of Addie LaRue",
  author: "V. E. Schwab",
  isbn: "9780765387561",
  asin: null,
  description: "A cursed immortal meets someone who remembers her.",
  cover_url: null,
  genre: "fantasy",
  genre_confidence: 0.93,
  genre_override: null,
  status: "scheduled",
  score: 2.0,
  packages: [PACKAGE],
};

const COST_SUMMARY = {
  total_cents: 17,
  total_usd: "0.17",
  by_call_name: {
    "llm.generate_hooks": { count: 1, cents: 0.5 },
    "llm.generate_script": { count: 1, cents: 2.0 },
    "images.generate": { count: 5, cents: 10.0 },
  },
  by_provider: { claude: 2.5, wanx: 10, openai: 4.5 },
  per_package: [
    {
      package_id: 1,
      book_id: 1,
      book_title: "The Invisible Life of Addie LaRue",
      revision_number: 1,
      cents: 17,
    },
  ],
  since: "2026-03-16T00:00:00",
  days: 30,
  record_count: 8,
  budget: { daily_cents: 500, today_cents: 17, remaining_cents: 483 },
};

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

async function wireBackend(page: Page) {
  // /items listing (renamed from /books in B7)
  await page.route(`${API}/items`, jsonRoute(BOOKS_LIST as unknown as Json));

  // Item detail (+365d cost lookup from /item route)
  await page.route(`${API}/items/1`, jsonRoute(BOOK_DETAIL as unknown as Json));

  // Cost summary (both settings-page and book-page variants)
  await page.route(
    new RegExp(`${API}/analytics/cost.*`),
    jsonRoute(COST_SUMMARY as unknown as Json),
  );

  // Discovery returns 2 new books; second /books fetch will then list them.
  await page.route(`${API}/discover/run`, jsonRoute({
    fetched: 2, created: 2, skipped: 0, new_source_rows: 2, per_source: {},
  }));
}

// ---------------------------------------------------------------------------
// tests
// ---------------------------------------------------------------------------

test("dashboard renders the queue heading", async ({ page }) => {
  await wireBackend(page);
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Book Queue" })).toBeVisible();
});

test("dashboard lists seeded books and links to detail", async ({ page }) => {
  await wireBackend(page);
  await page.goto("/dashboard");

  // Row visible with title + status chip
  const row = page.getByRole("row", { name: /Addie LaRue/i });
  await expect(row).toBeVisible();
  await expect(row.getByText("scheduled")).toBeVisible();

  // Opening via the title link hits /book?id=1
  await page.getByRole("link", { name: /Addie LaRue/i }).first().click();
  await expect(page).toHaveURL(/\/item\/?\?id=1$/);
});

test("book review page renders hook portfolio + section-labeled prompts", async ({ page }) => {
  await wireBackend(page);
  await page.goto("/item?id=1");

  // Header
  await expect(page.getByRole("heading", { name: "The Invisible Life of Addie LaRue" })).toBeVisible();

  // Hook portfolio: all 3 alternatives + the "chosen" pill
  for (const hook of HOOK_ALTERNATIVES) {
    await expect(page.getByText(hook.text, { exact: false })).toBeVisible();
  }
  // Exactly one "chosen" badge
  await expect(page.getByText("chosen", { exact: true })).toHaveCount(1);

  // Section chips on each prompt card
  for (const label of ["Hook", "World tease", "Emotional pull", "Social proof", "CTA"]) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }

  // Captions preview — count line
  await expect(page.getByText(/Captions — 5 words/i)).toBeVisible();

  // Cost badge (from mocked COST_SUMMARY.per_package)
  await expect(page.getByText("$0.17 spent")).toBeVisible();
});

test("render flow polls the job and shows the result", async ({ page }) => {
  await wireBackend(page);

  let pollCount = 0;
  await page.route(`${API}/packages/1/render?async=true`, jsonRoute({
    job_id: 42, status: "queued",
  }, 202));

  await page.route(`${API}/jobs/42`, (route) => {
    pollCount += 1;
    // First poll: running; second poll: succeeded (with the render result).
    const body = pollCount === 1
      ? { id: 42, kind: "render", target_id: 1, status: "running",
          message: "rendering: TTS + images + remotion", result: null,
          error: null, created_at: "2026-04-15T00:00:00", started_at: "2026-04-15T00:00:01",
          finished_at: null }
      : { id: 42, kind: "render", target_id: 1, status: "succeeded",
          message: "done", result: {
            package_id: 1,
            file_path: "/abs/path/out.mp4",
            duration_seconds: 58.2,
            size_bytes: 1_200_000,
            tone: "dark",
            work_dir: "/abs/path",
          },
          error: null, created_at: "2026-04-15T00:00:00",
          started_at: "2026-04-15T00:00:01", finished_at: "2026-04-15T00:01:30" };
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });

  await page.goto("/item?id=1");
  await page.getByRole("button", { name: /Render Video/i }).click();

  // While the job is "running" the button flips to "Rendering… rendering: TTS…"
  await expect(page.getByRole("button", { name: /Rendering/ })).toBeVisible();

  // After the second poll marks succeeded, the result card appears.
  await expect(page.getByText(/Rendered 58\.1s|Rendered 58\.2s/i)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/tone=dark/i)).toBeVisible();
  expect(pollCount).toBeGreaterThanOrEqual(2);
});

test("publish button surfaces the 501 as an inline error", async ({ page }) => {
  await wireBackend(page);
  await page.route(`${API}/publish/1/yt_shorts`, jsonRoute(
    { detail: "YouTube Shorts upload not yet wired — see services/youtube.py" },
    501,
  ));

  // Need a rendered state first — dispatch a quick successful render.
  await page.route(`${API}/packages/1/render?async=true`, jsonRoute({
    job_id: 7, status: "queued",
  }, 202));
  await page.route(`${API}/jobs/7`, jsonRoute({
    id: 7, kind: "render", target_id: 1, status: "succeeded", message: "done",
    result: {
      package_id: 1, file_path: "/out.mp4",
      duration_seconds: 58, size_bytes: 900_000, tone: "dark", work_dir: "/",
    },
    error: null, created_at: null, started_at: null, finished_at: null,
  }));

  await page.goto("/item?id=1");
  await page.getByRole("button", { name: /Render Video/i }).click();
  await expect(page.getByText(/Rendered/)).toBeVisible({ timeout: 10_000 });

  await page.getByRole("button", { name: /^YouTube Shorts$/ }).click();

  // Inline error message near the button
  await expect(page.getByText(/not yet wired/i)).toBeVisible();
});

test("settings page renders the cost summary + budget bar", async ({ page }) => {
  await wireBackend(page);
  await page.goto("/settings");

  // Headline total
  await expect(page.getByText("$0.17").first()).toBeVisible();

  // Budget: 17 / 500 cents → "$0.17 / $5.00"
  await expect(page.getByText(/\$0\.17 \/ \$5\.00/)).toBeVisible();

  // Provider rows (Claude and Wanx are the biggest)
  await expect(page.getByText("Claude")).toBeVisible();
  await expect(page.getByText("Wanx")).toBeVisible();
});
