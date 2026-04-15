export default function BookReviewPage({ params }: { params: { id: string } }) {
  return (
    <main className="mx-auto max-w-5xl p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold">Review Package</h1>
        <p className="text-sm opacity-70">Book ID: {params.id}</p>
      </header>

      <section className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="rounded-lg border border-white/10 p-6 md:col-span-2">
          <h2 className="mb-2 font-medium">90-sec script</h2>
          <p className="text-sm opacity-70">Placeholder — wired in Phase 1.</p>
        </div>

        <div className="rounded-lg border border-white/10 p-6">
          <h2 className="mb-2 font-medium">Visual prompts (4-5)</h2>
          <p className="text-sm opacity-70">Copy into your image provider.</p>
        </div>

        <div className="rounded-lg border border-white/10 p-6">
          <h2 className="mb-2 font-medium">Narration</h2>
          <p className="text-sm opacity-70">TTS-ready plain text.</p>
        </div>

        <div className="rounded-lg border border-white/10 p-6 md:col-span-2">
          <h2 className="mb-2 font-medium">Platform meta</h2>
          <p className="text-sm opacity-70">
            Titles + hashtags for TikTok, YouTube Shorts, Instagram Reels, Threads.
          </p>
        </div>
      </section>
    </main>
  );
}
