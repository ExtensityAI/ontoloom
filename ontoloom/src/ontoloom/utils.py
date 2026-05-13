import json
from collections.abc import Iterable


def dedupe[T](xs: Iterable[T]) -> list[T]:
    """Order-preserving deduplication."""
    return list(dict.fromkeys(xs))


def dquoted(s: object) -> str:
    """Double-quote `str(s)` for display, escaping embedded `"`, `\\`, and control chars."""
    return json.dumps(str(s), ensure_ascii=False)
