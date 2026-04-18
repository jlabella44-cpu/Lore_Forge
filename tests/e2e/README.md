# Playwright e2e

Full-flow happy-path test that walks through the Next.js UI with all
backend calls mocked via `page.route()`. No FastAPI / DB / LLM provider
required — we're asserting the UI consumes what the real backend would
send. The pytest suite covers the other side.

## Run locally

```bash
cd tests/e2e
npm install
npx playwright install chromium    # one-time browser download (~170MB)
npx playwright test
```

Playwright's `webServer` config spins up `npm run dev` in `../../frontend`
for the duration of the run (unless a dev server is already on :3000, in
which case it reuses that). First run takes ~30s for Next.js compile;
subsequent runs are fast.

## Coverage

`happy-path.spec.ts`:

- Dashboard renders the queue heading
- Dashboard lists books, row-click navigates to `/book?id=1`
- Book review page renders:
  - Hook portfolio (3 alternatives + "chosen" badge on one)
  - Section-labeled image prompts (Hook / World tease / Emotional pull /
    Social proof / CTA)
  - Captions preview with word count
  - Cost badge (`$0.17 spent`)
- Render flow: click → 202 enqueue → poll running → poll succeeded → result card
- Publish button surfaces a 501 as an inline error
- Settings page renders the 30-day summary + budget progress bar

## Not run in CI

This spec isn't part of the GitHub Actions workflow in `.github/workflows/ci.yml`
— the browser install + dev server boot add 2-3 minutes per run. Move it
in when that cost is worth the catch.
