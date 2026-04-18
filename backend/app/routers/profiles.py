"""Profile CRUD + YAML import/export.

Phase B6 of the generalization plan. Gives the frontend (and CLI
power-users) a way to list, inspect, edit, activate, and exchange
content profiles without hand-editing the JSON columns in SQLite.

URL map:
  GET    /profiles                — list all profiles (no secrets leak)
  GET    /profiles/active          — the currently active profile
  GET    /profiles/{slug}          — detail
  POST   /profiles                 — create from a payload
  POST   /profiles/import          — create/overwrite from YAML body
  PATCH  /profiles/{slug}          — partial update
  POST   /profiles/{slug}/activate — flip the `active=true` flag
  GET    /profiles/{slug}/export   — YAML dump suitable for version control
  DELETE /profiles/{slug}          — remove (refuses if profile is active)

YAML is the only serialization format — JSON over the wire is fine
for programmatic access, YAML is for humans reading/editing outside
the UI. The exported file is round-trip-able: import it again and you
get the same profile row.
"""
from __future__ import annotations

from typing import Any

import yaml
from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.profile import Profile
from app.services import profiles as profile_service


router = APIRouter()


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


_SERIALIZABLE_COLUMNS = (
    "slug",
    "name",
    "entity_label",
    "description",
    "sources_config",
    "prompts",
    "prompt_variables",
    "taxonomy",
    "cta_fields",
    "render_tones",
)


def _profile_to_dict(p: Profile) -> dict[str, Any]:
    """Shape the API returns — JSON-safe, stable across the router."""
    return {
        "id": p.id,
        "slug": p.slug,
        "name": p.name,
        "entity_label": p.entity_label,
        "description": p.description,
        "active": bool(p.active),
        "sources_config": p.sources_config or [],
        "prompts": p.prompts or {},
        "prompt_variables": p.prompt_variables or {},
        "taxonomy": p.taxonomy or [],
        "cta_fields": p.cta_fields or [],
        "render_tones": p.render_tones or {},
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _profile_to_yaml_dict(p: Profile) -> dict[str, Any]:
    """Stripped-down export — omits id, active, timestamps so a YAML
    file checked into a repo round-trips without churning on every
    upgrade (the receiving install assigns its own id + active flag).
    """
    out: dict[str, Any] = {}
    for col in _SERIALIZABLE_COLUMNS:
        val = getattr(p, col)
        if val in (None, "", [], {}):
            continue
        out[col] = val
    return out


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ProfileCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    entity_label: str = Field(..., min_length=1, max_length=64)
    description: str | None = None
    sources_config: list[dict] | None = None
    prompts: dict | None = None
    prompt_variables: dict | None = None
    taxonomy: list[str] | None = None
    cta_fields: list[dict] | None = None
    render_tones: dict | None = None


class ProfileUpdate(BaseModel):
    # Slug is immutable — renaming it would orphan every row with that
    # profile_id FK. A new profile import is the path for a rename.
    name: str | None = None
    entity_label: str | None = None
    description: str | None = None
    sources_config: list[dict] | None = None
    prompts: dict | None = None
    prompt_variables: dict | None = None
    taxonomy: list[str] | None = None
    cta_fields: list[dict] | None = None
    render_tones: dict | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
def list_profiles(db: Session = Depends(get_db)) -> list[dict]:
    return [_profile_to_dict(p) for p in profile_service.list_all(db)]


@router.get("/active")
def get_active(db: Session = Depends(get_db)) -> dict:
    active = profile_service.get_active(db)
    if active is None:
        raise HTTPException(status_code=404, detail="No active profile")
    return _profile_to_dict(active)


@router.get("/{slug}")
def get_profile(slug: str, db: Session = Depends(get_db)) -> dict:
    p = profile_service.get_by_slug(db, slug)
    if p is None:
        raise HTTPException(status_code=404, detail=f"Profile {slug!r} not found")
    return _profile_to_dict(p)


@router.post("", status_code=201)
def create_profile(body: ProfileCreate, db: Session = Depends(get_db)) -> dict:
    if profile_service.get_by_slug(db, body.slug) is not None:
        raise HTTPException(
            status_code=409, detail=f"Profile {body.slug!r} already exists"
        )
    p = Profile(
        slug=body.slug,
        name=body.name,
        entity_label=body.entity_label,
        description=body.description,
        active=False,
        sources_config=body.sources_config or [],
        prompts=body.prompts or {},
        prompt_variables=body.prompt_variables or {},
        taxonomy=body.taxonomy or [],
        cta_fields=body.cta_fields or [],
        render_tones=body.render_tones or {},
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _profile_to_dict(p)


@router.patch("/{slug}")
def update_profile(
    slug: str, body: ProfileUpdate, db: Session = Depends(get_db)
) -> dict:
    p = profile_service.get_by_slug(db, slug)
    if p is None:
        raise HTTPException(status_code=404, detail=f"Profile {slug!r} not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return _profile_to_dict(p)


@router.post("/{slug}/activate")
def activate_profile(slug: str, db: Session = Depends(get_db)) -> dict:
    try:
        target = profile_service.set_active(db, slug)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return _profile_to_dict(target)


@router.delete("/{slug}")
def delete_profile(slug: str, db: Session = Depends(get_db)) -> dict:
    p = profile_service.get_by_slug(db, slug)
    if p is None:
        raise HTTPException(status_code=404, detail=f"Profile {slug!r} not found")
    if p.active:
        raise HTTPException(
            status_code=409,
            detail=(
                "Refusing to delete the active profile; activate another "
                "profile first."
            ),
        )
    # Bail if anything still references this profile. Cascading
    # deletes across ContentItem → ContentPackage → Video is a lot of
    # fallout for one button; better to force the operator to move
    # items first or drop them explicitly.
    from app.models import ContentItem

    refs = db.query(ContentItem).filter(ContentItem.profile_id == p.id).count()
    if refs:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Refusing to delete profile {slug!r}: {refs} ContentItem "
                "rows still reference it."
            ),
        )
    db.delete(p)
    db.commit()
    return {"deleted": slug}


# ---------------------------------------------------------------------------
# YAML round-trip
# ---------------------------------------------------------------------------


@router.get("/{slug}/export")
def export_profile_yaml(slug: str, db: Session = Depends(get_db)) -> Response:
    p = profile_service.get_by_slug(db, slug)
    if p is None:
        raise HTTPException(status_code=404, detail=f"Profile {slug!r} not found")
    payload = yaml.safe_dump(
        _profile_to_yaml_dict(p),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    return Response(
        content=payload,
        media_type="application/x-yaml",
        headers={
            "Content-Disposition": f'attachment; filename="{slug}.yaml"'
        },
    )


@router.post("/import-bundle")
def import_bundled_examples(
    overwrite: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    """Import every YAML under `resources/profiles/` in one call.

    Convenience for bootstrapping a fresh install — the user gets
    movies, recipes, news (and whatever else ships) registered as
    inactive profiles they can activate from the dashboard without
    running a curl loop. The Books profile that 0009 seeded isn't
    touched.

    Returns `{imported: [slug], skipped: [slug]}`. `overwrite=true`
    replaces existing profiles; omit to leave user-edited profiles
    alone (they're reported under `skipped`).
    """
    from pathlib import Path

    # resources/ lives at the repo root. `app.config.REPO_ROOT` is
    # anchored there regardless of CWD, so every entry point (dev
    # uvicorn, packaged sidecar) finds the same directory.
    from app.config import REPO_ROOT

    bundle_dir = REPO_ROOT / "resources" / "profiles"
    if not bundle_dir.is_dir():
        raise HTTPException(
            status_code=500,
            detail=f"Bundle directory missing: {bundle_dir}",
        )

    imported: list[str] = []
    skipped: list[dict] = []
    for path in sorted(bundle_dir.glob("*.yaml")):
        try:
            parsed = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            skipped.append({"file": path.name, "reason": f"invalid YAML: {exc}"})
            continue
        if not isinstance(parsed, dict):
            skipped.append({"file": path.name, "reason": "top level not a mapping"})
            continue
        slug = parsed.get("slug")
        if not isinstance(slug, str) or not slug:
            skipped.append({"file": path.name, "reason": "missing slug"})
            continue

        existing = profile_service.get_by_slug(db, slug)
        if existing is not None and not overwrite:
            skipped.append({"file": path.name, "slug": slug, "reason": "exists"})
            continue

        # Reuse the single-file import logic for validation symmetry.
        if existing is None:
            target = Profile(slug=slug, name="", entity_label="", active=False)
            db.add(target)
        else:
            target = existing

        extra = set(parsed) - set(_SERIALIZABLE_COLUMNS)
        if extra:
            skipped.append(
                {
                    "file": path.name,
                    "slug": slug,
                    "reason": f"unknown keys {sorted(extra)}",
                }
            )
            db.rollback()
            continue

        for col in _SERIALIZABLE_COLUMNS:
            if col in parsed:
                setattr(target, col, parsed[col])
        db.commit()
        imported.append(slug)

    return {"imported": imported, "skipped": skipped}


@router.post("/import")
def import_profile_yaml(
    overwrite: bool = False,
    body: str = Body(..., media_type="application/x-yaml"),
    db: Session = Depends(get_db),
) -> dict:
    """Accepts the YAML dump produced by /export. Pass ?overwrite=true
    to replace an existing profile with the same slug; otherwise
    returns 409 on collision."""
    try:
        parsed = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=400, detail="YAML must parse to a mapping at the top level"
        )

    slug = parsed.get("slug")
    if not isinstance(slug, str) or not slug:
        raise HTTPException(status_code=400, detail="YAML missing string 'slug'")

    existing = profile_service.get_by_slug(db, slug)
    if existing is not None and not overwrite:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Profile {slug!r} already exists; pass ?overwrite=true to "
                "replace it."
            ),
        )

    # Build the Profile row. Unknown keys in the YAML are rejected so
    # typos in exported files surface immediately instead of silently
    # dropping prompts / taxonomy / etc.
    allowed = set(_SERIALIZABLE_COLUMNS)
    extra = set(parsed) - allowed
    if extra:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown YAML keys: {sorted(extra)}",
        )

    required = {"slug", "name", "entity_label"}
    missing = required - set(parsed)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"YAML missing required keys: {sorted(missing)}",
        )

    if existing is not None:
        target = existing
    else:
        target = Profile(slug=slug, name="", entity_label="", active=False)
        db.add(target)

    for col in _SERIALIZABLE_COLUMNS:
        if col in parsed:
            setattr(target, col, parsed[col])

    db.commit()
    db.refresh(target)
    return _profile_to_dict(target)
