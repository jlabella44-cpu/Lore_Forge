"""Content package generation + approval.

Synchronous by default (existing behavior). Pass `?async=true` on the
/generate and /render endpoints to get a 202 + job_id back and poll the
result via `GET /jobs/{id}`. Phase 3 can flip the frontend to always use
the async path once the polling UI is the default.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.context import package_context
from app.db import get_db
from app.models import Book, ContentPackage
from app.models.format import VideoFormat
from app.observability import log_call
from app.services import amazon, cost, jobs, llm, renderer, render_retention
from app.services.prompts import get_bundle

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /books/{id}/generate[?async=true]
# ---------------------------------------------------------------------------

@router.post("/books/generate-all")
def generate_all(
    response: Response = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
) -> dict:
    """Enqueue an async generate job for every book that's `discovered` and
    has no ContentPackage yet. Always returns 202 + the list of job ids;
    the frontend polls each to show aggregate progress.

    Hits the daily-budget guardrail once up front; if we're already at the
    cap, no jobs enqueue and the response is 429.
    """
    try:
        cost.assert_under_budget()
    except cost.BudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    # Eligible: status=discovered AND no existing package on this book.
    packaged_ids = {
        row[0]
        for row in db.query(ContentPackage.book_id).distinct().all()
    }
    eligible = (
        db.query(Book)
        .filter(Book.status == "discovered")
        .order_by(Book.score.desc(), Book.id.asc())
        .all()
    )
    eligible = [b for b in eligible if b.id not in packaged_ids]

    job_ids: list[int] = []
    for book in eligible:
        job_id = jobs.enqueue(
            "generate",
            book.id,
            _generate_worker,
            book_id=book.id,
            note=None,
        )
        job_ids.append(job_id)

    if response is not None:
        response.status_code = 202
    return {
        "enqueued": len(job_ids),
        "eligible_count": len(eligible),
        "job_ids": job_ids,
    }


@router.post("/books/{book_id}/generate")
def generate_package(
    book_id: int,
    payload: dict | None = None,
    response: Response = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    asynchronous: bool = Query(False, alias="async"),
) -> dict:
    """Create a new ContentPackage revision. Body: {"note": "..."} optional.

    Synchronous by default. Pass `?async=true` to enqueue and get back
    `{job_id, status: "queued"}` with HTTP 202 — poll GET /jobs/{job_id}.
    """
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    note = (payload or {}).get("note")

    try:
        cost.assert_under_budget()
    except cost.BudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    if asynchronous:
        job_id = jobs.enqueue(
            "generate",
            book_id,
            _generate_worker,
            book_id=book_id,
            note=note,
        )
        if response is not None:
            response.status_code = 202
        return {"job_id": job_id, "status": "queued"}

    return _generate_sync(db, book, book_id, note)


# ---------------------------------------------------------------------------
# POST /packages/render-all
# ---------------------------------------------------------------------------

@router.post("/packages/render-all")
def render_all(
    response: Response = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
) -> dict:
    """Enqueue an async render for every book in `scheduled` (approved but
    not yet rendered). Returns 202 + job_ids.

    Parallel to `/books/generate-all`: hits the daily-budget guardrail once
    up front, picks candidates in score order, enqueues each via the
    existing render worker. Books in `rendered` or `published` are skipped
    — re-rendering happens one package at a time via the per-package
    endpoint (narration edits flip `needs_rerender` on the package, not
    the book status).
    """
    try:
        cost.assert_under_budget()
    except cost.BudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    # Eligible: book.status=scheduled + has an approved package.
    eligible_pkgs = (
        db.query(ContentPackage)
        .join(Book, Book.id == ContentPackage.book_id)
        .filter(Book.status == "scheduled", ContentPackage.is_approved.is_(True))
        .order_by(Book.score.desc(), ContentPackage.id.asc())
        .all()
    )

    job_ids: list[int] = []
    for pkg in eligible_pkgs:
        job_id = jobs.enqueue(
            "render", pkg.id, _render_worker, package_id=pkg.id
        )
        job_ids.append(job_id)

    if response is not None:
        response.status_code = 202
    return {
        "enqueued": len(job_ids),
        "eligible_count": len(eligible_pkgs),
        "job_ids": job_ids,
    }


# ---------------------------------------------------------------------------
# POST /packages/{id}/render[?async=true]
# ---------------------------------------------------------------------------

@router.post("/packages/{package_id}/render")
def render_package(
    package_id: int,
    response: Response = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    asynchronous: bool = Query(False, alias="async"),
) -> dict:
    """Run the full render pipeline for an approved package.

    Synchronous by default (blocks 1-3 minutes on real providers). Pass
    `?async=true` for the 202 + poll flow.
    """
    package = db.get(ContentPackage, package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Package not found")
    if not package.is_approved:
        raise HTTPException(
            status_code=400, detail="Package must be approved before rendering"
        )
    book = db.get(Book, package.book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    try:
        cost.assert_under_budget()
    except cost.BudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    if asynchronous:
        job_id = jobs.enqueue(
            "render", package_id, _render_worker, package_id=package_id
        )
        if response is not None:
            response.status_code = 202
        return {"job_id": job_id, "status": "queued"}

    try:
        with package_context(package_id):
            result = renderer.render_package(package, book)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"package_id": package_id, **result}


# ---------------------------------------------------------------------------
# POST /packages/prune-renders
# ---------------------------------------------------------------------------

@router.post("/packages/prune-renders")
def prune_renders(
    max_age_days: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
) -> dict:
    """Delete on-disk renders + clear render-metadata for never-published
    packages older than `max_age_days`. Defaults to `settings.render_retention_days`
    (30); set to 0 or negative in config to disable the endpoint entirely.

    Also LRU-prunes the image asset cache using
    `settings.image_cache_retention_days` (independent knob), so stale
    per-prompt blobs don't leak disk indefinitely. The image-cache sweep
    is best-effort — a failure there doesn't roll back the renders prune.
    """
    days = max_age_days if max_age_days is not None else settings.render_retention_days
    if days <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Render retention is disabled "
                "(RENDER_RETENTION_DAYS <= 0); pass ?max_age_days=N to override."
            ),
        )
    result = render_retention.prune_stale_renders(db, max_age_days=days)

    cache_days = settings.image_cache_retention_days
    if cache_days > 0:
        result["image_cache"] = render_retention.prune_stale_image_cache(
            db, max_age_days=cache_days
        )
    return result


# ---------------------------------------------------------------------------
# POST /packages/{id}/approve
# ---------------------------------------------------------------------------

@router.post("/packages/{package_id}/approve")
def approve_package(package_id: int, db: Session = Depends(get_db)) -> dict:
    """Approve one revision — un-approves any prior approved revision for the
    same book so there's always a single canonical approved package."""
    package = db.get(ContentPackage, package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Package not found")

    (
        db.query(ContentPackage)
        .filter(
            ContentPackage.book_id == package.book_id,
            ContentPackage.id != package_id,
        )
        .update({"is_approved": False}, synchronize_session=False)
    )
    package.is_approved = True

    book = db.get(Book, package.book_id)
    if book is not None:
        book.status = "scheduled"

    db.commit()
    return {"ok": True, "package_id": package_id}


# ---------------------------------------------------------------------------
# Workers — the sync path calls the same logic inline; the async path runs
# it inside jobs.job_session which owns the Job row's lifecycle.
# ---------------------------------------------------------------------------

def _generate_sync(db: Session, book: Book, book_id: int, note: str | None) -> dict:
    genre = book.genre_override or book.genre or "other"
    previous_status = book.status
    book.status = "generating"
    db.commit()
    try:
        with cost.collect_pending() as pending_cost_ids:
            result = _generate_core(db, book, genre, note)
        cost.attach_pending_to(result["package_id"], pending_cost_ids)
        book.status = "review"
        db.commit()
        return {
            "package_id": result["package_id"],
            "revision_number": result["revision_number"],
        }
    except Exception as exc:
        db.rollback()
        book = db.get(Book, book_id)
        if book is not None:
            book.status = previous_status
            db.commit()
        raise HTTPException(status_code=502, detail=f"Generation failed: {exc}") from exc


def _generate_worker(job_id: int, *, book_id: int, note: str | None) -> None:
    with jobs.job_session(job_id) as (db, set_progress):
        book = db.get(Book, book_id)
        if book is None:
            raise RuntimeError(f"Book {book_id} not found")
        genre = book.genre_override or book.genre or "other"
        previous_status = book.status
        book.status = "generating"
        db.commit()
        try:
            set_progress("Stage 1/4: hook portfolio")
            with cost.collect_pending() as pending_cost_ids:
                result = _generate_core_with_progress(
                    db, book, genre, note, set_progress
                )
            cost.attach_pending_to(result["package_id"], pending_cost_ids)
            book.status = "review"
            db.commit()
            set_progress.result(result)
        except Exception:
            db.rollback()
            book = db.get(Book, book_id)
            if book is not None:
                book.status = previous_status
                db.commit()
            raise


def _render_worker(job_id: int, *, package_id: int) -> None:
    with jobs.job_session(job_id) as (db, set_progress):
        package = db.get(ContentPackage, package_id)
        if package is None:
            raise RuntimeError(f"Package {package_id} not found")
        book = db.get(Book, package.book_id)
        if book is None:
            raise RuntimeError(f"Book {package.book_id} not found")
        # Render-time services can read package_id directly — the package
        # already exists so cost records get attached at write time.
        with package_context(package_id):
            result = renderer.render_package(package, book, on_progress=set_progress)
        set_progress.result({"package_id": package_id, **result})


# ---------------------------------------------------------------------------
# Core generation logic (shared by both paths)
# ---------------------------------------------------------------------------

def _generate_core(
    db: Session, book: Book, genre: str, note: str | None,
    fmt: str = "short_hook",
) -> dict:
    return _generate_core_with_progress(db, book, genre, note, lambda _msg: None, fmt=fmt)


def _generate_core_with_progress(
    db: Session,
    book: Book,
    genre: str,
    note: str | None,
    set_progress,
    *,
    fmt: str = "short_hook",
    series_id: int | None = None,
    part_number: int | None = None,
    books_for_list: list[Book] | None = None,
) -> dict:
    """Run the staged LLM pipeline, format-aware.

    For SHORT_HOOK: uses the original 4-stage pipeline (hooks → script →
    scene prompts → meta). `book` is the single target.

    For LIST: skips hooks (the concept IS the hook), generates a list script
    from `books_for_list`, scene prompts per book, and meta. `book` is
    treated as the "anchor" for affiliate links / revision tracking.
    """
    bundle = get_bundle(fmt)

    with log_call(
        "generate.pipeline",
        book_id=book.id,
        genre=genre,
        has_note=bool(note),
        format=fmt,
    ):
        if fmt == "short_hook":
            result_pkg = _pipeline_short_hook(book, genre, note, set_progress)
        elif fmt == "list":
            result_pkg = _pipeline_list(
                book, genre, note, set_progress, books_for_list or [], bundle
            )
        else:
            raise ValueError(f"No pipeline implemented for format {fmt!r}")

        affiliate_amazon, affiliate_bookshop = _affiliate_links(book.isbn)

        last_revision = (
            db.query(func.max(ContentPackage.revision_number))
            .filter(ContentPackage.book_id == book.id)
            .scalar()
            or 0
        )
        package = ContentPackage(
            book_id=book.id,
            revision_number=last_revision + 1,
            script=result_pkg["script"],
            narration=result_pkg["narration"],
            section_word_counts=result_pkg.get("section_word_counts"),
            hook_alternatives=result_pkg.get("hook_alternatives"),
            chosen_hook_index=result_pkg.get("chosen_hook_index"),
            visual_prompts=result_pkg["visual_prompts"],
            titles=result_pkg["titles"],
            hashtags=result_pkg["hashtags"],
            affiliate_amazon=affiliate_amazon,
            affiliate_bookshop=affiliate_bookshop,
            regenerate_note=note,
            is_approved=False,
            format=fmt,
            series_id=series_id,
            part_number=part_number,
        )
        db.add(package)
        # Commit (not just flush) so SQLite releases the write lock before
        # attach_pending_to fires. Otherwise the outer session holds an
        # open write-txn while attach_pending_to opens a NEW session to
        # UPDATE cost_records, and SQLite's single-writer constraint
        # blocks it for busy_timeout and then errors.
        db.commit()
        db.refresh(package)
        return {
            "package_id": package.id,
            "revision_number": package.revision_number,
        }


# ---------------------------------------------------------------------------
# Per-format pipelines
# ---------------------------------------------------------------------------

def _pipeline_short_hook(
    book: Book, genre: str, note: str | None, set_progress,
) -> dict:
    """Original 4-stage pipeline for single-book short-hook videos."""
    set_progress("Stage 1/4: hook portfolio")
    hooks = llm.generate_hooks(
        title=book.title,
        author=book.author,
        description=book.description,
        genre=genre,
    )
    chosen_hook_text = hooks["alternatives"][hooks["chosen_index"]]["text"]

    set_progress("Stage 2/4: writing script")
    script_pkg = llm.generate_script(
        title=book.title,
        author=book.author,
        description=book.description,
        genre=genre,
        chosen_hook=chosen_hook_text,
        note=note,
    )

    set_progress("Stage 3/4: scene prompts")
    scene_pkg = llm.generate_scene_prompts(
        script=script_pkg["script"], genre=genre
    )

    set_progress("Stage 4/4: per-platform meta")
    meta = llm.generate_platform_meta(
        script=script_pkg["script"], genre=genre
    )

    return {
        "script": script_pkg["script"],
        "narration": script_pkg["narration"],
        "section_word_counts": script_pkg["section_word_counts"],
        "hook_alternatives": hooks["alternatives"],
        "chosen_hook_index": hooks["chosen_index"],
        "visual_prompts": scene_pkg["scenes"],
        "titles": meta["titles"],
        "hashtags": meta["hashtags"],
    }


def _pipeline_list(
    anchor_book: Book,
    genre: str,
    note: str | None,
    set_progress,
    books: list[Book],
    bundle,
) -> dict:
    """LIST format: intro → N book mini-pitches → CTA."""
    if not books:
        raise ValueError("LIST format requires at least one book in books_for_list")

    book_lines = []
    for i, b in enumerate(books, 1):
        book_lines.append(
            f"Book {i}: {b.title} by {b.author}\n"
            f"  Description: {b.description or '(none)'}"
        )
    user_text = (
        f"List title: Top {len(books)} {genre.replace('_', ' ').title()} Reads\n"
        f"Genre: {genre}\n\n"
        + "\n\n".join(book_lines)
    )
    if note:
        user_text += f"\n\nRevision note: {note}"

    set_progress("Stage 1/3: list script")
    script_pkg = llm.dispatch(
        "script",
        bundle.script.system,
        user_text,
        bundle.script.tool_name,
        bundle.script.schema,
    )

    set_progress("Stage 2/3: scene prompts per book")
    scene_pkg = llm.dispatch(
        "script",
        bundle.scene_prompts.system,
        f"Books in the list:\n{user_text}\n\nScript:\n{script_pkg['script']}",
        bundle.scene_prompts.tool_name,
        bundle.scene_prompts.schema,
    )

    set_progress("Stage 3/3: per-platform meta")
    meta = llm.dispatch(
        "meta",
        bundle.meta.system,
        f"Genre: {genre}\n\nScript:\n{script_pkg['script']}",
        bundle.meta.tool_name,
        bundle.meta.schema,
    )

    return {
        "script": script_pkg["script"],
        "narration": script_pkg["narration"],
        "section_word_counts": script_pkg.get("book_word_counts"),
        "hook_alternatives": None,
        "chosen_hook_index": None,
        "visual_prompts": scene_pkg["scenes"],
        "titles": meta["titles"],
        "hashtags": meta["hashtags"],
    }


def _affiliate_links(isbn: str | None) -> tuple[str | None, str | None]:
    if not isbn:
        return None, None
    amazon_url = None
    if settings.amazon_associate_tag:
        try:
            asin = amazon.lookup_asin(isbn)
            if asin:
                amazon_url = amazon.build_affiliate_url(asin)
        except Exception:
            pass
    bookshop_url = None
    if settings.bookshop_affiliate_id:
        try:
            bookshop_url = amazon.build_bookshop_url(isbn)
        except Exception:
            pass
    return amazon_url, bookshop_url
