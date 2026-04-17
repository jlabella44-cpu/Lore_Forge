"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  BarChart3,
  Layers,
  Settings,
  Flame,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Books", icon: BookOpen },
  { href: "/series", label: "Series", icon: Layers },
  { href: "/settings", label: "Costs", icon: BarChart3 },
  { href: "/analytics", label: "Analytics", icon: Settings },
] as const;

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-56 flex-col border-r border-white/[0.06] bg-[hsl(222,47%,9%)]">
      {/* Brand */}
      <div className="flex h-14 items-center gap-2.5 px-5 border-b border-white/[0.06]">
        <Flame className="h-5 w-5 text-amber-400" />
        <span className="text-[15px] font-semibold tracking-tight text-white">
          Lore Forge
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-3 space-y-0.5">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active =
            pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={`
                group flex items-center gap-2.5 rounded-md px-2.5 py-[7px] text-[13px] font-medium transition-colors
                ${
                  active
                    ? "bg-white/[0.08] text-white"
                    : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
                }
              `}
            >
              <Icon
                className={`h-[15px] w-[15px] flex-shrink-0 ${
                  active ? "text-amber-400" : "text-slate-500 group-hover:text-slate-400"
                }`}
              />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-white/[0.06] px-4 py-3">
        <p className="text-[11px] text-slate-600">
          Book content pipeline
        </p>
      </div>
    </aside>
  );
}
