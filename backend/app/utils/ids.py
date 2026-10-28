from typing import Union
from uuid import UUID


def to_uuid(value: Union[str, UUID]) -> UUID:
    """Return `value` as a UUID.

    Routers hand services either `str(current_user.id)` or a UUID; UUID
    columns need real UUID objects on every dialect (SQLite and PostgreSQL).
    Raises ValueError for malformed strings.
    """
    return value if isinstance(value, UUID) else UUID(str(value))
