"""Background job runner for generate + render.

Phase 2+ lives inside a single uvicorn process, so we keep this dead simple:
threading-based execution with a pluggable submit hook so tests can run
inline without spawning real threads.

Each enqueued job gets a row in the `jobs` table immediately. The worker
opens its own SessionLocal (the HTTP request's session is closed before
the task runs) and walks the row through queued → running → succeeded |
failed, calling `set_progress(job_id, msg)` between stages so the UI can
show what's happening.

Example:

    def generate_worker(job_id: int, item_id: int):
        with job_session(job_id) as (db, set_progress):
            set_progress("classifying…")
            ...
            set_progress("writing script…")
            ...
            return {"package_id": pkg.id}

    job_id = jobs.enqueue("generate", item_id, generate_worker, item_id)
    # → client gets {job_id}; polls GET /jobs/{job_id}
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from app import db as _db_module  # use module attr so tests can swap SessionLocal
from app.clock import utc_now
from app.models import Job
from app.observability import get_logger

logger = get_logger("jobs")


# Tests replace this with `lambda fn: fn()` so jobs run inline + the HTTP
# response can be polled immediately.
def _default_submit(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, daemon=True).start()


_submit: Callable[[Callable[[], None]], None] = _default_submit


def set_submit_hook(hook: Callable[[Callable[[], None]], None]) -> None:
    """Override how enqueued jobs are run. Tests use this for inline
    execution. Returns the previous hook so the caller can restore."""
    global _submit
    _submit = hook


def reset_submit_hook() -> None:
    global _submit
    _submit = _default_submit


def enqueue(kind: str, target_id: int, worker: Callable[..., Any], *args, **kwargs) -> int:
    """Create a Job row and submit `worker(job_id, *args, **kwargs)` to run
    in the background. Returns the job id synchronously.

    `worker` is responsible for calling `job_session()` to get its DB +
    progress handle; this keeps the enqueue path free of the job-lifecycle
    boilerplate.
    """
    db = _db_module.SessionLocal()
    try:
        job = Job(
            kind=kind,
            target_id=target_id,
            status="queued",
            created_at=utc_now(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    finally:
        db.close()

    def _run() -> None:
        try:
            worker(job_id, *args, **kwargs)
        except BaseException as exc:
            # Last-ditch: mark failed so we never leave a job stuck in
            # running forever. job_session already handles this for
            # exceptions from within it, but this covers anything raised
            # *before* the session opens.
            logger.exception("%s job %d crashed before starting", kind, job_id)
            _mark_failed(job_id, repr(exc))

    _submit(_run)
    return job_id


@contextmanager
def job_session(job_id: int) -> Iterator[tuple[Any, Callable[[str], None]]]:
    """Open a DB session, flip the Job to running, and yield (db, set_progress).

    On normal exit the job is flipped to `succeeded` with the worker's
    return value stored in `result`. On exception the job is flipped to
    `failed` with the exception text in `error`. The session is committed
    and closed automatically.
    """
    db = _db_module.SessionLocal()
    set_progress = _make_set_progress(db, job_id)

    job = db.get(Job, job_id)
    if job is None:
        db.close()
        raise RuntimeError(f"Job {job_id} vanished before run")

    job.status = "running"
    job.started_at = utc_now()
    job.message = "running"
    db.commit()

    try:
        result_holder: dict[str, Any] = {}
        yield db, _progress_and_result(set_progress, result_holder)
    except BaseException as exc:
        logger.exception("job %d failed", job_id)
        db.rollback()
        job = db.get(Job, job_id)
        if job is not None:
            job.status = "failed"
            job.error = str(exc) or repr(exc)
            job.finished_at = utc_now()
            db.commit()
        db.close()
        raise
    else:
        job = db.get(Job, job_id)
        if job is not None:
            job.status = "succeeded"
            job.result = result_holder.get("value")
            job.message = "done"
            job.finished_at = utc_now()
            db.commit()
        db.close()


def _make_set_progress(db, job_id: int) -> Callable[[str], None]:
    def set_progress(msg: str) -> None:
        job = db.get(Job, job_id)
        if job is not None:
            job.message = msg
            db.commit()

    return set_progress


def _progress_and_result(set_progress, result_holder):
    """Wrap set_progress with a .result() method so workers can stash their
    return value. Using a closure avoids having to pass result_holder
    through every worker signature."""

    class _Progress:
        def __call__(self, msg: str) -> None:
            set_progress(msg)

        def result(self, value: Any) -> None:
            result_holder["value"] = value

    return _Progress()


def _mark_failed(job_id: int, error: str) -> None:
    db = _db_module.SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = "failed"
        job.error = error
        job.finished_at = utc_now()
        db.commit()
    finally:
        db.close()
