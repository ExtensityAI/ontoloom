import json
from collections.abc import Iterable


def dedupe[T](xs: Iterable[T]) -> list[T]:
    """Order-preserving deduplication."""
    return list(dict.fromkeys(xs))


def dquoted(s: str) -> str:
    """Double-quote `s` for display, escaping embedded `"`, `\\`, and control chars."""
    return json.dumps(s, ensure_ascii=False)
