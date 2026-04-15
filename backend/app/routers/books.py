from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Book

router = APIRouter()


@router.get("")
def list_books(db: Session = Depends(get_db)) -> list[dict]:
    books = db.query(Book).order_by(Book.score.desc()).all()
    return [
        {
            "id": b.id,
            "title": b.title,
            "author": b.author,
            "genre": b.genre_override or b.genre,
            "score": b.score,
            "status": b.status,
        }
        for b in books
    ]


@router.patch("/{book_id}")
def update_book(book_id: int, payload: dict, db: Session = Depends(get_db)) -> dict:
    """Phase 1: supports genre override. Extend as needed."""
    book = db.get(Book, book_id)
    if book is None:
        return {"error": "not found"}
    if "genre_override" in payload:
        book.genre_override = payload["genre_override"]
    db.commit()
    return {"ok": True}
