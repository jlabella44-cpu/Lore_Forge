import { Chip, type ChipVariant } from "./Chip";

const STATUS_MAP: Record<string, { label: string; variant: ChipVariant }> = {
  discovered: { label: "Discovered", variant: "plain" },
  generating: { label: "Generating", variant: "warn" },
  review: { label: "Review", variant: "info" },
  scheduled: { label: "Scheduled", variant: "accent" },
  rendered: { label: "Rendered", variant: "accent" },
  published: { label: "Published", variant: "ok" },
  skipped: { label: "Skipped", variant: "plain" },
};

export function StatusChip({ status }: { status: string }) {
  const entry = STATUS_MAP[status] ?? { label: status, variant: "plain" as const };
  return <Chip variant={entry.variant}>{entry.label}</Chip>;
}
