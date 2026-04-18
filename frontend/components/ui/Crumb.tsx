import Link from "next/link";
import { ChevronLeft } from "lucide-react";

export function Crumb({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="mb-3 inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-fg-3 transition-colors hover:text-fg-1"
    >
      <ChevronLeft className="h-3 w-3" />
      {label}
    </Link>
  );
}
