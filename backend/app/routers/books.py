from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Book, ContentPackage

router = APIRouter()


@router.get("")
def list_books(db: Session = Depends(get_db)) -> list[dict]:
    books = db.query(Book).order_by(Book.score.desc(), Book.id.desc()).all()
    return [
        {
            "id": b.id,
            "title": b.title,
            "author": b.author,
            "cover_url": b.cover_url,
            "genre": b.genre_override or b.genre,
            "genre_source": "override" if b.genre_override else "auto",
            "genre_confidence": b.genre_confidence,
            "score": b.score,
            "status": b.status,
        }
        for b in books
    ]


@router.get("/{book_id}")
def get_book(book_id: int, db: Session = Depends(get_db)) -> dict:
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    packages = (
        db.query(ContentPackage)
        .filter(ContentPackage.book_id == book_id)
        .order_by(ContentPackage.revision_number.desc())
        .all()
    )

    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "isbn": book.isbn,
        "asin": book.asin,
        "description": book.description,
        "cover_url": book.cover_url,
        "genre": book.genre,
        "genre_confidence": book.genre_confidence,
        "genre_override": book.genre_override,
        "status": book.status,
        "score": book.score,
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
            }
            for p in packages
        ],
    }


@router.patch("/{book_id}")
def update_book(
    book_id: int,
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    """Phase 1 supports genre_override only."""
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    if "genre_override" in payload:
        book.genre_override = payload["genre_override"] or None
    db.commit()
    return {"ok": True}
