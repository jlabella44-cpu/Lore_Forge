export default function DashboardPage() {
  return (
    <main className="mx-auto max-w-6xl p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold">Book Queue</h1>
        <p className="text-sm opacity-70">
          Discovered books ranked by score. Click a row to review its content package.
        </p>
      </header>

      <section className="rounded-lg border border-white/10 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-medium">Queue is empty</h2>
            <p className="text-sm opacity-70">
              Run discovery to populate the queue.
            </p>
          </div>
          <button
            className="rounded-md bg-white/10 px-4 py-2 text-sm hover:bg-white/20"
            disabled
          >
            Run NYT Discovery
          </button>
        </div>
      </section>
    </main>
  );
}
