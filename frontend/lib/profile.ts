"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";

/** Sliver of the /profiles/active response the UI cares about for
 *  label rendering. The full Profile shape is bigger; pull only what
 *  the dashboard / sidebar / page heads need. */
export type ActiveProfile = {
  slug: string;
  name: string;
  entity_label: string;
};

/** Fetch the active profile once on mount. Returns null while loading
 *  or if no profile is active. Callers should pluralize via `pluralize`
 *  when they need the noun in plural form ("Books", "Films", "Recipes").
 */
export function useActiveProfile(): ActiveProfile | null {
  const [profile, setProfile] = useState<ActiveProfile | null>(null);
  useEffect(() => {
    apiFetch<ActiveProfile>("/profiles/active")
      .then(setProfile)
      .catch(() => {
        // No active profile (404) or backend unreachable — caller falls
        // back to the generic "Item" copy.
      });
  }, []);
  return profile;
}

/** Naive English pluralization: "Book" → "Books", "Recipe" → "Recipes",
 *  "Headline" → "Headlines". Handles the s / x / z / ch / sh + es case.
 *  Profile authors who need irregulars (Geese, Children) can override
 *  by setting `entity_label` to the plural form and accepting that the
 *  singular contexts ("Edit Book") will look slightly off. */
export function pluralize(word: string): string {
  if (!word) return word;
  const lower = word.toLowerCase();
  if (
    lower.endsWith("s") ||
    lower.endsWith("x") ||
    lower.endsWith("z") ||
    lower.endsWith("ch") ||
    lower.endsWith("sh")
  ) {
    return `${word}es`;
  }
  if (lower.endsWith("y") && !/[aeiou]y$/i.test(word)) {
    return `${word.slice(0, -1)}ies`;
  }
  return `${word}s`;
}
