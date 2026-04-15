"""Per-request context that service-layer code can read without having to
thread IDs through every signature.

Currently holds: the active package_id during generate/render pipelines so
`services/cost.py` can attach CostRecord rows to the right package.

`set_package_id` returns the token for reset — use it as a context manager
via `with package_context(id):` for guaranteed cleanup on exceptions.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_package_id: ContextVar[int | None] = ContextVar("lore_package_id", default=None)


def get_package_id() -> int | None:
    return _package_id.get()


@contextmanager
def package_context(package_id: int | None) -> Iterator[None]:
    token = _package_id.set(package_id)
    try:
        yield
    finally:
        _package_id.reset(token)
