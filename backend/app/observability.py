"""Structured logging helpers.

Long-running operations (generate, render) take tens of seconds to minutes —
without logs, the user stares at a spinner. This module gives every external
call and every pipeline stage a consistent enter/exit log line with timing
and useful structured fields.

Configured once at app startup via `configure_logging()` in main.py.

Usage from a service:

    from app.observability import log_call

    with log_call("llm.generate_hooks", genre="fantasy"):
        ...

    # Add more structured fields mid-operation:
    with log_call("renderer.render_package", package_id=42) as ctx:
        ctx["scene_count"] = 5
        ctx["tone"] = tone
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator


# Per-component logger. Each service imports `logger` via `get_logger()`.
def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"loreforge.{name}")


def configure_logging(level: int | str = logging.INFO) -> None:
    """Idempotent root-logger configuration. Safe to call multiple times —
    uvicorn --reload will invoke it repeatedly and we don't want duplicate
    handlers stacking up."""
    root = logging.getLogger("loreforge")
    if getattr(root, "_lore_configured", False):
        root.setLevel(level)
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
    root._lore_configured = True  # type: ignore[attr-defined]


@contextmanager
def log_call(name: str, **fields: Any) -> Iterator[dict[str, Any]]:
    """Log `name → ok in Ns` (or `name → error in Ns` on raise) with the
    given structured fields. Yields a mutable dict so the body can append
    more fields before the exit line fires.
    """
    logger = get_logger(name.split(".")[0])
    bag: dict[str, Any] = dict(fields)
    start = time.monotonic()
    logger.info("%s → start %s", name, _fmt(bag))
    try:
        yield bag
    except BaseException as exc:
        elapsed = time.monotonic() - start
        logger.error(
            "%s → error in %.2fs %s exc=%s",
            name,
            elapsed,
            _fmt(bag),
            exc,
        )
        raise
    else:
        elapsed = time.monotonic() - start
        logger.info("%s → ok in %.2fs %s", name, elapsed, _fmt(bag))


def _fmt(fields: dict[str, Any]) -> str:
    if not fields:
        return ""
    return " ".join(f"{k}={v}" for k, v in fields.items())
