from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.clock import utc_now
from app.db import Base


class Profile(Base):
    """A user-configurable content niche (books, movies, recipes, news, ...).

    Phase B generalizes the pipeline: instead of hard-coding "book trailer"
    assumptions in prompts, discovery sources, and the dashboard, each
    piece of behaviour reads from the currently-active `Profile` row.

    One profile is `active=True` at any time (UI switches between them).
    The Books profile is seeded by migration 0009 so existing installs
    keep working byte-for-byte with nothing to configure.

    JSON columns (shape is intentionally loose — later migrations tighten
    as real usage clarifies):

      * `sources_config` — list of `{plugin_slug, config}` dicts driving
        discovery. For Books this maps to the existing
        `app/sources/{nyt,goodreads,...}.py` plugin slugs.
      * `prompts` — Jinja2 templates per LLM stage (hook_system,
        script_system, scene_prompts_system, meta_system). Rendered
        with profile-specific variables (entity_type, tone, banned_words).
      * `taxonomy` — list of category strings that replace hard-coded
        genre enums in the UI + LLM classification.
      * `cta_fields` — list of `{key, label}` describing the CTA link
        columns on each ContentPackage (books: amazon_url, bookshop_url;
        movies: trailer_url, streaming_url; ...).
      * `render_tones` — category → tone string map (e.g. "fantasy":
        "dark"). Passed to the renderer for music + composition picks.
    """

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), index=True, unique=True)
    name: Mapped[str] = mapped_column(String(200))

    # Singular noun shown in the UI wherever "Book" was hard-coded.
    # e.g. "Book", "Film", "Recipe", "Headline".
    entity_label: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Exactly one row should have `active=True`. Enforced in application
    # code (profile service) rather than a partial unique index so the
    # constraint translates to every DB backend.
    active: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )

    sources_config: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    prompts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    taxonomy: Mapped[list | None] = mapped_column(JSON, nullable=True)
    cta_fields: Mapped[list | None] = mapped_column(JSON, nullable=True)
    render_tones: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )
