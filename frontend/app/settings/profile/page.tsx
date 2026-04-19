"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

import { apiFetch, type Profile, type ProfileUpdate } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHead } from "@/components/ui/PageHead";

export default function ProfileEditPageWrapper() {
  // `useSearchParams` requires a Suspense boundary under static export.
  return (
    <Suspense fallback={<LoadingShell />}>
      <ProfileEditPage />
    </Suspense>
  );
}

function LoadingShell() {
  return (
    <div className="mx-auto max-w-[960px] px-10 pb-20 pt-9">
      <Card className="text-sm text-fg-3">Loading…</Card>
    </div>
  );
}

function ProfileEditPage() {
  const searchParams = useSearchParams();
  const slug = searchParams.get("slug") ?? "";

  const [profile, setProfile] = useState<Profile | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Editable form state — text-serialised copies of the JSON/list fields so
  // the user can type freely even through a syntax error.
  const [name, setName] = useState("");
  const [entityLabel, setEntityLabel] = useState("");
  const [description, setDescription] = useState("");
  const [taxonomyText, setTaxonomyText] = useState("");
  const [promptsText, setPromptsText] = useState("");
  const [promptVariablesText, setPromptVariablesText] = useState("");
  const [sourcesConfigText, setSourcesConfigText] = useState("");
  const [ctaFieldsText, setCtaFieldsText] = useState("");
  const [renderTonesText, setRenderTonesText] = useState("");

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!slug) {
      setLoadError("Missing slug query param");
      return;
    }
    try {
      setLoadError(null);
      const p = await apiFetch<Profile>(
        `/profiles/${encodeURIComponent(slug)}`,
      );
      setProfile(p);
      setName(p.name ?? "");
      setEntityLabel(p.entity_label ?? "");
      setDescription(p.description ?? "");
      setTaxonomyText((p.taxonomy ?? []).join("\n"));
      setPromptsText(stringifyJson(p.prompts));
      setPromptVariablesText(stringifyJson(p.prompt_variables));
      setSourcesConfigText(stringifyJson(p.sources_config));
      setCtaFieldsText(stringifyJson(p.cta_fields));
      setRenderTonesText(stringifyJson(p.render_tones));
    } catch (e) {
      setLoadError(String(e));
    }
  }, [slug]);

  useEffect(() => {
    load();
  }, [load]);

  // Clear the "Saved" flash after two seconds so it's unambiguously
  // tied to the last successful save rather than lingering indefinitely.
  useEffect(() => {
    if (savedAt === null) return;
    const handle = setTimeout(() => setSavedAt(null), 2000);
    return () => clearTimeout(handle);
  }, [savedAt]);

  const { body, validationError } = useMemo(
    () =>
      buildPatchBody({
        profile,
        name,
        entityLabel,
        description,
        taxonomyText,
        promptsText,
        promptVariablesText,
        sourcesConfigText,
        ctaFieldsText,
        renderTonesText,
      }),
    [
      profile,
      name,
      entityLabel,
      description,
      taxonomyText,
      promptsText,
      promptVariablesText,
      sourcesConfigText,
      ctaFieldsText,
      renderTonesText,
    ],
  );

  const hasChanges = body !== null && Object.keys(body).length > 0;

  const save = useCallback(async () => {
    if (!profile || body === null) return;
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await apiFetch<Profile>(
        `/profiles/${encodeURIComponent(profile.slug)}`,
        { method: "PATCH", body: JSON.stringify(body) },
      );
      setProfile(updated);
      setSavedAt(Date.now());
    } catch (e) {
      setSaveError(String(e));
    } finally {
      setSaving(false);
    }
  }, [profile, body]);

  if (loadError) {
    return (
      <div className="mx-auto max-w-[960px] px-10 pb-20 pt-9">
        <div className="rounded-lg border border-err/30 bg-err-soft p-4 text-sm text-[oklch(90%_0.12_25)]">
          {loadError}
        </div>
        <div className="mt-4">
          <Link href="/settings/profiles">
            <Button>← Back to profiles</Button>
          </Link>
        </div>
      </div>
    );
  }

  if (!profile) {
    return <LoadingShell />;
  }

  return (
    <div className="mx-auto max-w-[960px] px-10 pb-20 pt-9">
      <PageHead
        eyebrow={profile.active ? "Active profile" : "Profile"}
        title={`Edit ${profile.name}`}
        lede={`Slug ${profile.slug} · immutable. The backend rejects slug renames; import a new YAML to rename.`}
      />

      {saveError && (
        <div className="mb-6 rounded-lg border border-err/30 bg-err-soft p-4 text-sm text-[oklch(90%_0.12_25)]">
          {saveError}
        </div>
      )}

      {validationError && (
        <div className="mb-6 rounded-lg border border-warn/30 bg-warn-soft p-4 text-sm text-[oklch(92%_0.1_85)]">
          {validationError}
        </div>
      )}

      <Card className="space-y-6">
        <Field label="Name">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field
          label="Entity label"
          hint="Singular noun the UI pluralises ('Book', 'Film', 'Recipe')."
        >
          <input
            type="text"
            value={entityLabel}
            onChange={(e) => setEntityLabel(e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Description">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            className={inputClass}
          />
        </Field>

        <Field
          label="Taxonomy"
          hint="One genre/category per line. Powers the classify step."
        >
          <textarea
            value={taxonomyText}
            onChange={(e) => setTaxonomyText(e.target.value)}
            rows={6}
            spellCheck={false}
            className={textareaMonoClass}
          />
        </Field>

        <JsonField
          label="Prompts"
          hint="Jinja-templated LLM prompts keyed by role (classify, script, …)."
          value={promptsText}
          onChange={setPromptsText}
        />

        <JsonField
          label="Prompt variables"
          hint="Named fragments interpolated into prompts via {{ var }}."
          value={promptVariablesText}
          onChange={setPromptVariablesText}
        />

        <JsonField
          label="Sources config"
          hint="Plugin stack for /discover/run — list of {type, params} objects."
          value={sourcesConfigText}
          onChange={setSourcesConfigText}
        />

        <JsonField
          label="CTA fields"
          hint="Per-profile CTA definitions that drive the cta_links JSON on each item."
          value={ctaFieldsText}
          onChange={setCtaFieldsText}
        />

        <JsonField
          label="Render tones"
          hint="Per-tone visual presets for the renderer."
          value={renderTonesText}
          onChange={setRenderTonesText}
        />

        <div className="flex items-center justify-end gap-3 border-t border-hair pt-5">
          {savedAt !== null && (
            <span
              className="font-mono text-[11px] uppercase tracking-[0.12em]"
              style={{ color: "var(--accent)" }}
            >
              Saved
            </span>
          )}
          <Link href="/settings/profiles">
            <Button variant="ghost" size="md">
              Cancel
            </Button>
          </Link>
          <Button
            variant="primary"
            disabled={!hasChanges || saving || validationError !== null}
            onClick={save}
          >
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const inputClass =
  "w-full rounded-md border border-hair bg-white/[0.02] px-3 py-2 text-[13.5px] text-fg-1 outline-none transition-colors focus:border-hair-strong focus:bg-white/[0.04]";

const textareaMonoClass =
  "w-full rounded-md border border-hair bg-white/[0.02] px-3 py-2 font-mono text-[12px] text-fg-1 outline-none transition-colors focus:border-hair-strong focus:bg-white/[0.04]";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="mb-1.5 font-mono text-[10.5px] uppercase tracking-[0.14em] text-fg-3">
        {label}
      </div>
      {children}
      {hint && <div className="mt-1 text-[11.5px] text-fg-4">{hint}</div>}
    </label>
  );
}

function JsonField({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const parseError = parseJsonError(value);
  return (
    <div>
      <Field label={label} hint={hint}>
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={8}
          spellCheck={false}
          className={textareaMonoClass}
          style={
            parseError
              ? { borderColor: "oklch(70% 0.15 25 / 0.4)" }
              : undefined
          }
        />
      </Field>
      {parseError && (
        <div className="mt-1 font-mono text-[11px] text-[oklch(78%_0.14_25)]">
          JSON: {parseError}
        </div>
      )}
    </div>
  );
}

function stringifyJson(value: unknown): string {
  if (value === null || value === undefined) return "";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "";
  }
}

function parseJsonError(text: string): string | null {
  const trimmed = text.trim();
  if (trimmed === "") return null;
  try {
    JSON.parse(trimmed);
    return null;
  } catch (e) {
    return e instanceof Error ? e.message : String(e);
  }
}

/** Parse the raw textareas into a PATCH body that only contains fields
 *  the user actually changed. Returns `validationError` for any JSON
 *  syntax mistake so the caller can block save. */
function buildPatchBody(args: {
  profile: Profile | null;
  name: string;
  entityLabel: string;
  description: string;
  taxonomyText: string;
  promptsText: string;
  promptVariablesText: string;
  sourcesConfigText: string;
  ctaFieldsText: string;
  renderTonesText: string;
}): { body: ProfileUpdate | null; validationError: string | null } {
  const p = args.profile;
  if (p === null) return { body: null, validationError: null };

  const body: ProfileUpdate = {};

  if (args.name !== (p.name ?? "")) body.name = args.name;
  if (args.entityLabel !== (p.entity_label ?? ""))
    body.entity_label = args.entityLabel;

  const description = args.description === "" ? null : args.description;
  if (description !== (p.description ?? null)) {
    body.description = description;
  }

  const taxonomy = args.taxonomyText
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (!arraysShallowEqual(taxonomy, p.taxonomy ?? [])) {
    body.taxonomy = taxonomy;
  }

  const jsonFields: Array<{
    key: "prompts" | "prompt_variables" | "sources_config" | "cta_fields" | "render_tones";
    text: string;
    current: unknown;
    emptyDefault: unknown;
  }> = [
    { key: "prompts", text: args.promptsText, current: p.prompts, emptyDefault: {} },
    {
      key: "prompt_variables",
      text: args.promptVariablesText,
      current: p.prompt_variables,
      emptyDefault: {},
    },
    {
      key: "sources_config",
      text: args.sourcesConfigText,
      current: p.sources_config,
      emptyDefault: [],
    },
    {
      key: "cta_fields",
      text: args.ctaFieldsText,
      current: p.cta_fields,
      emptyDefault: [],
    },
    {
      key: "render_tones",
      text: args.renderTonesText,
      current: p.render_tones,
      emptyDefault: {},
    },
  ];

  for (const field of jsonFields) {
    const trimmed = field.text.trim();
    let parsed: unknown;
    if (trimmed === "") {
      parsed = field.emptyDefault;
    } else {
      try {
        parsed = JSON.parse(trimmed);
      } catch (e) {
        return {
          body: null,
          validationError: `${field.key}: ${e instanceof Error ? e.message : String(e)}`,
        };
      }
    }
    if (JSON.stringify(parsed) !== JSON.stringify(field.current ?? field.emptyDefault)) {
      // Double-casting because TS's index-signature variance gets
      // awkward across the five field shapes; the backend validates
      // each field again anyway.
      (body as Record<string, unknown>)[field.key] = parsed;
    }
  }

  return { body, validationError: null };
}

function arraysShallowEqual<T>(a: T[], b: T[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}
