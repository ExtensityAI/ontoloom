import json
from collections.abc import Hashable, Iterable, Sequence
from itertools import chain


def dedupe[T](xs: Iterable[T]) -> list[T]:
    """Order-preserving deduplication."""
    return list(dict.fromkeys(xs))


def union_ordered[T: Hashable](*sequences: Sequence[T]) -> list[T]:
    """First-seen-order union across all sequences."""
    return list(dict.fromkeys(chain.from_iterable(sequences)))


def intersect_ordered[T: Hashable](first: Sequence[T], *rest: Sequence[T]) -> list[T]:
    """Items of `first` (first-seen order) present in every other sequence."""
    rest_sets = [set(r) for r in rest]
    return [x for x in dict.fromkeys(first) if all(x in r for r in rest_sets)]


def difference_ordered[T: Hashable](first: Sequence[T], *rest: Sequence[T]) -> list[T]:
    """Items of `first` (first-seen order) absent from all other sequences."""
    removed = set(chain.from_iterable(rest))
    return [x for x in dict.fromkeys(first) if x not in removed]


def dquoted(s: object) -> str:
    """Double-quote `str(s)` for display, escaping embedded `"`, `\\`, and control chars."""
    return json.dumps(str(s), ensure_ascii=False)
