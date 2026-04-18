from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.clock import utc_now
from app.db import Base


class ContentItem(Base):
    """A discovered piece of content the pipeline can generate a short for.

    Replaces the book-specific `Book` model introduced in 0001. The
    generic shape — title, subtitle, description, cover, status, score —
    is niche-agnostic: every profile (books, films, recipes, news, ...)
    fits the same columns. Profile-specific payload lives in the
    `research` JSON blob, shaped by whatever the active profile's
    research step populates. For the Books profile, that's the
    pre-generalization set: isbn, asin, genre, genre_confidence,
    genre_override, dossier (migrated in place by 0010).

    Lifecycle: discovered → generating → review → scheduled → rendered
    → published, plus the `skipped` side-state. Unchanged from the
    Book era.
    """

    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id"), index=True
    )

    title: Mapped[str] = mapped_column(String(500))
    # Generic secondary label: "author" for books, "director" for films,
    # "cuisine" for recipes. Renamed from `author` in migration 0010.
    subtitle: Mapped[str] = mapped_column(String(300))
    cover_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    description: Mapped[str | None] = mapped_column(String(4000), nullable=True)

    status: Mapped[str] = mapped_column(
        String(32), default="discovered", server_default="discovered"
    )
    score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")

    # Per-profile research blob. Populated by the active profile's
    # research stage on first generate, cached so downstream LLM stages
    # can cite concrete details instead of generic filler. Books stores:
    # {isbn, asin, genre, genre_confidence, genre_override, dossier}.
    research: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # ------------------------------------------------------------------
    # Books-era convenience accessors.
    #
    # Many services still call `item.genre`, `item.isbn`, `item.dossier`
    # from the book era. Each is a read/write view over the research
    # blob so the rest of the codebase can migrate to `item.research`
    # at its own pace. A profile that wants a differently-shaped
    # research blob simply doesn't touch these keys.
    # ------------------------------------------------------------------

    def _research_get(self, key: str):
        return (self.research or {}).get(key)

    def _research_set(self, key: str, value) -> None:
        # Reassigning the whole dict triggers SQLAlchemy dirty tracking;
        # mutating in place does not.
        cur = dict(self.research or {})
        if value is None:
            cur.pop(key, None)
        else:
            cur[key] = value
        self.research = cur or None

    @property
    def isbn(self) -> str | None:
        return self._research_get("isbn")

    @isbn.setter
    def isbn(self, value: str | None) -> None:
        self._research_set("isbn", value)

    @property
    def asin(self) -> str | None:
        return self._research_get("asin")

    @asin.setter
    def asin(self, value: str | None) -> None:
        self._research_set("asin", value)

    @property
    def genre(self) -> str | None:
        return self._research_get("genre")

    @genre.setter
    def genre(self, value: str | None) -> None:
        self._research_set("genre", value)

    @property
    def genre_confidence(self) -> float | None:
        return self._research_get("genre_confidence")

    @genre_confidence.setter
    def genre_confidence(self, value: float | None) -> None:
        self._research_set("genre_confidence", value)

    @property
    def genre_override(self) -> str | None:
        return self._research_get("genre_override")

    @genre_override.setter
    def genre_override(self, value: str | None) -> None:
        self._research_set("genre_override", value)

    @property
    def dossier(self) -> dict | None:
        return self._research_get("dossier")

    @dossier.setter
    def dossier(self, value: dict | None) -> None:
        self._research_set("dossier", value)
