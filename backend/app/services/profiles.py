"""Active-profile lookup + activation.

The `profiles` table (see migration 0009) holds one row per content
niche. Exactly one row is `active=True` at any point in time; the
dashboard and pipeline read that row to decide what "entity" means
(book/film/recipe/...), which discovery sources run, which prompts
fire, and what CTA fields show up on the package.

This module is the single writer of the `active` column.
Do not flip `profile.active` directly elsewhere — it would desync the
"exactly one active" invariant.

`get_active()` returns None only in two cases:
  1. Migration hasn't run yet (brand-new DB before 0009).
  2. A user manually toggled every profile inactive.
Callers handling Book-era flows should treat None as "fall back to
hard-coded Books defaults" so the app stays functional while the
generalization lands piece by piece.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.profile import Profile


def get_active(db: Session) -> Profile | None:
    return db.query(Profile).filter(Profile.active.is_(True)).one_or_none()


def get_by_slug(db: Session, slug: str) -> Profile | None:
    return db.query(Profile).filter(Profile.slug == slug).one_or_none()


def list_all(db: Session) -> list[Profile]:
    return db.query(Profile).order_by(Profile.slug.asc()).all()


def set_active(db: Session, slug: str) -> Profile:
    """Flip `active=True` on the matching profile, `False` on every
    other row. Raises LookupError if the slug doesn't exist.

    Commit is the caller's responsibility — keeps this composable with
    larger transactions (e.g. "import profile, then activate it").
    """
    target = get_by_slug(db, slug)
    if target is None:
        raise LookupError(f"profile {slug!r} not found")

    # Two-step: clear everyone, then set the winner. Cheaper than
    # iterating the result set in Python; safe because the transaction
    # is atomic.
    db.query(Profile).filter(Profile.slug != slug).update(
        {Profile.active: False}, synchronize_session=False
    )
    target.active = True
    db.flush()
    return target
