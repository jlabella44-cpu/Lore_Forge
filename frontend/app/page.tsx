"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Server-side `redirect()` doesn't round-trip through the static export
// cleanly (there's no server to issue a 307), so the root just bounces
// client-side on mount. Users who land here in a Tauri window see a
// blank flash for ~1 frame before the dashboard paints.
export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);
  return null;
}
