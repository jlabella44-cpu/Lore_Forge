"""Single source of truth for "now" in UTC.

`datetime.utcnow()` is deprecated in Python 3.12+. The recommended replacement
is `datetime.now(timezone.utc)`, which returns a timezone-aware value. We
strip the tzinfo to keep the database side naive (the DateTime columns are
defined without `timezone=True`), so the DB shape is unchanged and all prior
stored values remain directly comparable.
"""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Timezone-naive UTC timestamp — matches the pre-3.12 `datetime.utcnow()`
    shape that all our DateTime columns were designed against."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
