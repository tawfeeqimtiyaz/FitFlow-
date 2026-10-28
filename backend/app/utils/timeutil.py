from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Return `value` as an aware UTC datetime.

    SQLite hands back naive datetimes even for timezone-aware columns, while
    PostgreSQL returns aware ones; naive values are UTC in both cases.
    """
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
