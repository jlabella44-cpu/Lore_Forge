"""ContentItem CRUD — the renamed successor of the books router.

URL path stays at `/books` for now — the frontend hasn't caught up to
the ContentItem rename yet. B7 neutralizes the URL prefix and the
response keys (`author` → `subtitle`, `book_id` → `content_item_id`).
Until then, the API shape matches the pre-B2 contract so the dashboard
keeps working unchanged.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ContentItem, ContentPackage
from app.services.renderer import narration_hash

router = APIRouter()


def _needs_rerender(package: ContentPackage) -> bool:
    """True when either (a) the package has never rendered, or (b) the
    narration has been edited since the last render so the on-disk mp4 is
    stale. A package with no narration at all can't render yet — we treat
    that as "needs render" too."""
    if package.rendered_at is None:
        return True
    if not package.narration:
        return True
    return narration_hash(package.narration) != (package.rendered_narration_hash or "")


@router.get("")
def list_items(
    include_skipped: bool = False,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Default: hides items with status='skipped'. Pass `?include_skipped=true`
    to list them too (used by the settings / admin surface)."""
    q = db.query(ContentItem).order_by(ContentItem.score.desc(), ContentItem.id.desc())
    if not include_skipped:
        q = q.filter(ContentItem.status != "skipped")
    items = q.all()
    return [
        {
            "id": it.id,
            "title": it.title,
            "author": it.subtitle,
            "cover_url": it.cover_url,
            "genre": it.genre_override or it.genre,
            "genre_source": "override" if it.genre_override else "auto",
            "genre_confidence": it.genre_confidence,
            "score": it.score,
            "status": it.status,
        }
        for it in items
    ]


@router.get("/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)) -> dict:
    item = db.get(ContentItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    packages = (
        db.query(ContentPackage)
        .filter(ContentPackage.content_item_id == item_id)
        .order_by(ContentPackage.revision_number.desc())
        .all()
    )

    return {
        "id": item.id,
        "title": item.title,
        "author": item.subtitle,
        "isbn": item.isbn,
        "asin": item.asin,
        "description": item.description,
        "cover_url": item.cover_url,
        "genre": item.genre,
        "genre_confidence": item.genre_confidence,
        "genre_override": item.genre_override,
        "status": item.status,
        "score": item.score,
        "dossier": item.dossier,
        "packages": [
            {
                "id": p.id,
                "revision_number": p.revision_number,
                "script": p.script,
                "narration": p.narration,
                "hook_alternatives": p.hook_alternatives,
                "chosen_hook_index": p.chosen_hook_index,
                "visual_prompts": p.visual_prompts,
                "section_word_counts": p.section_word_counts,
                "captions": p.captions,
                "titles": p.titles,
                "hashtags": p.hashtags,
                "affiliate_amazon": p.affiliate_amazon,
                "affiliate_bookshop": p.affiliate_bookshop,
                "regenerate_note": p.regenerate_note,
                "is_approved": p.is_approved,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "rendered_at": p.rendered_at.isoformat() if p.rendered_at else None,
                "rendered_duration_seconds": p.rendered_duration_seconds,
                "rendered_size_bytes": p.rendered_size_bytes,
                "needs_rerender": _needs_rerender(p),
            }
            for p in packages
        ],
    }


@router.patch("/{item_id}")
def update_item(
    item_id: int,
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    """Editable fields: genre_override, status, dossier.

    `dossier`: pass a dict to replace it wholesale, or `null` to clear it
    (next /generate call will then rebuild from scratch via the LLM).
    """
    item = db.get(ContentItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if "genre_override" in payload:
        item.genre_override = payload["genre_override"] or None
    if "status" in payload:
        item.status = payload["status"]
    if "dossier" in payload:
        value = payload["dossier"]
        if value is not None and not isinstance(value, dict):
            raise HTTPException(
                status_code=400,
                detail="dossier must be a JSON object or null",
            )
        item.dossier = value
    db.commit()
    return {"ok": True}


@router.post("/{item_id}/skip")
def skip_item(item_id: int, db: Session = Depends(get_db)) -> dict:
    """Mark an item as skipped — hidden from the default queue."""
    item = db.get(ContentItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    item.status = "skipped"
    db.commit()
    return {"ok": True, "status": "skipped"}


@router.post("/{item_id}/unskip")
def unskip_item(item_id: int, db: Session = Depends(get_db)) -> dict:
    """Reverse of /skip — puts the item back in `discovered` state."""
    item = db.get(ContentItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    item.status = "discovered"
    db.commit()
    return {"ok": True, "status": "discovered"}
