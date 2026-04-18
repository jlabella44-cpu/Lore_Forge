# Example content profiles

Each YAML file in this directory is a starter profile you can import
into a running Lore Forge install. The Books profile ships seeded by
migration 0009 — everything else is opt-in so the default dashboard
stays focused.

## Import a profile

```
curl -X POST http://localhost:8000/profiles/import \
  -H 'Content-Type: application/x-yaml' \
  --data-binary @movies.yaml
```

Append `?overwrite=true` to replace an existing profile with the same
slug. Freshly-imported profiles are always inactive; activate with:

```
curl -X POST http://localhost:8000/profiles/movies/activate
```

## Shipped examples

| File          | Niche         | Discovery source plugin | CTA fields |
|---------------|---------------|-------------------------|------------|
| `movies.yaml` | Film trailers | `rss_feed` (IndieWire, /Film) | trailer, streaming, IMDb |
| `recipes.yaml`| Recipe reels  | `manual_input` (paste-in list) | blog, Pinterest, Substack |
| `news.yaml`   | Tech-news recaps | `rss_feed` (The Verge, TechCrunch) | article, newsletter |

These are starting points. The right workflow is:

1. Import one — `curl --data-binary @movies.yaml ...`
2. Run discovery once, generate a draft short, eyeball the output.
3. Edit the profile through `PATCH /profiles/movies` (or the upcoming
   editor UI) until the prompts + CTAs + tones feel right.
4. Export via `GET /profiles/movies/export` and commit the result
   back to your fork so the next install starts from your tuned version.

## Shape

Every profile YAML is a mapping with these keys:

- `slug` (required) — short id (`films`, `bookish-romance`, ...).
  Immutable after import — a rename is a new import with the old row
  deleted.
- `name`, `entity_label` (required) — display strings.
- `description` — free-form.
- `sources_config` — list of `{plugin_slug, config}`. See
  `backend/app/sources/` for the available plugins.
- `prompts` — per-stage system-prompt templates (`hook_system`,
  `script_system`, `scene_prompts_system`, `meta_system`). Jinja2
  variables are resolved at rendering time by `prompt_renderer`.
- `taxonomy` — list of category slugs used in place of the Books-era
  genre enum.
- `cta_fields` — list of `{key, label}` slots the review UI will
  offer for each ContentPackage's `cta_links` JSON.
- `render_tones` — category → tone map (`dark`, `hype`, `cozy`) passed
  to the renderer for music + composition picks.

## Contributing

Want to share a profile for a niche you've tuned (romance-booktok,
Japanese car scene, film-scoring breakdowns)? Drop the YAML in this
directory with a PR. No code changes needed.
