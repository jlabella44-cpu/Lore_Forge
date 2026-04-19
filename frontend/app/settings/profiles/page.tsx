"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { apiFetch, apiUrl, type Profile } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHead } from "@/components/ui/PageHead";

export default function ProfilesListPage() {
  const [profiles, setProfiles] = useState<Profile[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingSlug, setPendingSlug] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setError(null);
      const list = await apiFetch<Profile[]>("/profiles");
      setProfiles(list);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const activate = useCallback(
    async (slug: string) => {
      setPendingSlug(slug);
      try {
        await apiFetch(`/profiles/${slug}/activate`, { method: "POST" });
        await reload();
      } catch (e) {
        setError(String(e));
      } finally {
        setPendingSlug(null);
      }
    },
    [reload],
  );

  const remove = useCallback(
    async (slug: string) => {
      if (!confirm(`Delete profile "${slug}"?`)) return;
      setPendingSlug(slug);
      try {
        await apiFetch(`/profiles/${slug}`, { method: "DELETE" });
        await reload();
      } catch (e) {
        setError(String(e));
      } finally {
        setPendingSlug(null);
      }
    },
    [reload],
  );

  return (
    <div className="mx-auto max-w-[1240px] px-10 pb-20 pt-9">
      <PageHead
        eyebrow="Operations"
        title="Content profiles"
        lede="The active profile drives prompts, sources, CTAs, and render tones. Activate, edit, or delete profiles here; import bundles via the CLI."
      />

      {error && (
        <div className="mb-6 rounded-lg border border-err/30 bg-err-soft p-4 text-sm text-[oklch(90%_0.12_25)]">
          {error}
        </div>
      )}

      {!profiles ? (
        <Card className="text-sm text-fg-3">Loading…</Card>
      ) : profiles.length === 0 ? (
        <Card className="text-center text-sm text-fg-3">
          <p className="mb-1">No profiles registered.</p>
          <p className="font-mono text-[11px]">
            python -m app.profile_cli import-bundle
          </p>
        </Card>
      ) : (
        <Card className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b border-hair text-left font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
              <tr>
                <th className="px-5 py-3 w-10">Active</th>
                <th className="px-5 py-3">Name</th>
                <th className="px-5 py-3">Entity</th>
                <th className="px-5 py-3">Slug</th>
                <th className="px-5 py-3 text-right">Sources</th>
                <th className="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((p) => (
                <ProfileRow
                  key={p.slug}
                  profile={p}
                  pending={pendingSlug === p.slug}
                  onActivate={() => activate(p.slug)}
                  onDelete={() => remove(p.slug)}
                />
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

function ProfileRow({
  profile,
  pending,
  onActivate,
  onDelete,
}: {
  profile: Profile;
  pending: boolean;
  onActivate: () => void;
  onDelete: () => void;
}) {
  const sourceCount = Array.isArray(profile.sources_config)
    ? profile.sources_config.length
    : 0;
  return (
    <tr className="border-b border-hair last:border-0">
      <td className="px-5 py-3">
        {profile.active ? (
          <span
            aria-label="Active"
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: "var(--accent)" }}
          />
        ) : (
          <span
            aria-label="Inactive"
            className="inline-block h-2 w-2 rounded-full bg-white/[0.08]"
          />
        )}
      </td>
      <td className="px-5 py-3">
        <div className="text-fg-1">{profile.name}</div>
        {profile.description && (
          <div className="mt-0.5 truncate text-[11.5px] text-fg-4">
            {profile.description}
          </div>
        )}
      </td>
      <td className="px-5 py-3 text-fg-2">{profile.entity_label}</td>
      <td className="px-5 py-3 font-mono text-[11.5px] text-fg-3">
        {profile.slug}
      </td>
      <td className="px-5 py-3 text-right font-mono text-fg-2 tabular-nums">
        {sourceCount}
      </td>
      <td className="px-5 py-3">
        <div className="flex items-center justify-end gap-1.5">
          {!profile.active && (
            <Button
              size="sm"
              variant="primary"
              disabled={pending}
              onClick={onActivate}
            >
              Activate
            </Button>
          )}
          <Link href={`/settings/profile?slug=${encodeURIComponent(profile.slug)}`}>
            <Button size="sm">Edit</Button>
          </Link>
          <a
            href={apiUrl(`/profiles/${encodeURIComponent(profile.slug)}/export`)}
            download={`${profile.slug}.yaml`}
          >
            <Button size="sm" variant="ghost">
              Export
            </Button>
          </a>
          {!profile.active && (
            <Button
              size="sm"
              variant="ghost"
              disabled={pending}
              onClick={onDelete}
            >
              Delete
            </Button>
          )}
        </div>
      </td>
    </tr>
  );
}
