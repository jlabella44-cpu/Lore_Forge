import { describe, expect, it } from "vitest";

import { formatBytes, formatDuration, formatTimeAgo } from "./format";

describe("formatDuration", () => {
  it("rounds sub-minute durations to whole seconds", () => {
    expect(formatDuration(0)).toBe("0s");
    expect(formatDuration(47)).toBe("47s");
    expect(formatDuration(47.4)).toBe("47s");
    expect(formatDuration(47.6)).toBe("48s");
  });

  it("renders minutes with no remainder as bare minutes", () => {
    expect(formatDuration(60)).toBe("1m");
    expect(formatDuration(180)).toBe("3m");
  });

  it("renders minutes with leftover seconds", () => {
    expect(formatDuration(90)).toBe("1m 30s");
    expect(formatDuration(125)).toBe("2m 5s");
  });
});

describe("formatBytes", () => {
  it("renders tiny values in raw bytes", () => {
    expect(formatBytes(0)).toBe("0B");
    expect(formatBytes(1023)).toBe("1023B");
  });

  it("renders KB without decimals", () => {
    expect(formatBytes(1024)).toBe("1KB");
    expect(formatBytes(2048)).toBe("2KB");
    expect(formatBytes(1024 * 500)).toBe("500KB");
  });

  it("renders MB with one decimal", () => {
    expect(formatBytes(1024 * 1024)).toBe("1.0MB");
    expect(formatBytes(12 * 1024 * 1024)).toBe("12.0MB");
    expect(formatBytes(1.5 * 1024 * 1024)).toBe("1.5MB");
  });
});

describe("formatTimeAgo", () => {
  const now = Date.parse("2026-04-20T12:00:00Z");

  it("collapses the last minute to 'just now'", () => {
    expect(formatTimeAgo("2026-04-20T11:59:30Z", now)).toBe("just now");
    expect(formatTimeAgo("2026-04-20T12:00:00Z", now)).toBe("just now");
  });

  it("reports minutes under an hour", () => {
    expect(formatTimeAgo("2026-04-20T11:55:00Z", now)).toBe("5m ago");
    expect(formatTimeAgo("2026-04-20T11:01:00Z", now)).toBe("59m ago");
  });

  it("reports hours under a day", () => {
    expect(formatTimeAgo("2026-04-20T09:00:00Z", now)).toBe("3h ago");
    expect(formatTimeAgo("2026-04-19T13:00:00Z", now)).toBe("23h ago");
  });

  it("reports days at and above 24 hours", () => {
    expect(formatTimeAgo("2026-04-19T12:00:00Z", now)).toBe("1d ago");
    expect(formatTimeAgo("2026-04-13T12:00:00Z", now)).toBe("7d ago");
  });
});
