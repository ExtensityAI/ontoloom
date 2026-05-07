"""Search axioms using pattern matching, integrated with DB and selections."""

from __future__ import annotations

import typing
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated, get_args, get_origin

from ontoloom.canonical import SKIP
from ontoloom.connection import Ontology
from ontoloom.hashing import HASH_DISPLAY_LEN
from ontoloom.load import load_axiom
from ontoloom.models import FrozenModel
from ontoloom.owl.axioms import Axiom
from ontoloom.owl.expressions import ClassExpression
from ontoloom.owl.iri import IRI
from ontoloom.patterns import ExpressionPattern
from ontoloom.patterns.base import BasePattern
from ontoloom.patterns.match import _match_pattern
from ontoloom.patterns.slot import Slot
from ontoloom.selections.store import get_selection
from ontoloom.selections.types import SelectionKind


@dataclass
class MatchResult:
    """Result of a pattern match search.

    `truncated=True` means iteration stopped at `limit`; more matches may exist.
    """

    axiom_hashes: list[str]
    total: int
    truncated: bool = False


def match_axioms(
    ont: Ontology,
    pattern: BasePattern,
    *,
    within: str | None = None,
    limit: int | None = None,
) -> MatchResult:
    """Find axioms matching a pattern. Returns matched hashes.

    For axiom-level patterns, filters candidates by axiom type.
    For expression-level patterns, searches all axioms (or scoped set).
    `limit` caps the number of matches collected; iteration stops early when hit.
    """
    matched_hashes: list[str] = []
    truncated = False
    for h, json_data in _iter_candidates(ont, pattern, within):
        axiom = load_axiom(json_data, f"match {h[:HASH_DISPLAY_LEN]}")
        if _match_pattern(pattern, axiom):
            matched_hashes.append(h)
            if limit is not None and len(matched_hashes) >= limit:
                truncated = True
                break
    return MatchResult(
        axiom_hashes=matched_hashes,
        total=len(matched_hashes),
        truncated=truncated,
    )


_EXPRESSION_PATTERN_CLASSES: tuple[type, ...] = get_args(ExpressionPattern)

def _peel(member: object) -> type:
    # Axiom union members are Annotated[Cls, Tag("...")] for callable-discriminator wiring.
    return get_args(member)[0] if get_origin(member) is Annotated else member  # pyright: ignore[reportReturnType]


_AXIOM_CLASSES: tuple[type, ...] = tuple(_peel(m) for m in get_args(get_args(Axiom)[0]))
# The raw ClassExpression union (no Annotated wrapper). Annotated[ClassExpression, marker]
# flattens via PEP 593, so checking args[0] is _EXPR_UNION is the correct identity test.
_EXPR_UNION = get_args(ClassExpression)[0]


def _annotation_has_expr_union(tp: object) -> bool:
    if get_origin(tp) is Annotated:
        args = get_args(tp)
        return args[0] is _EXPR_UNION or _annotation_has_expr_union(args[0])
    if get_origin(tp) is tuple:
        return any(_annotation_has_expr_union(a) for a in get_args(tp))
    return False


def _has_class_expression_field(cls: type) -> bool:
    hints = typing.get_type_hints(cls, include_extras=True)
    return any(
        _annotation_has_expr_union(hints[f])
        for f in cls.model_fields
        if f not in ("type", "annotations")
    )


_EXPRESSION_CONTAINER_TYPES = frozenset(
    cls.tag() for cls in _AXIOM_CLASSES if _has_class_expression_field(cls)
)


def _iter_candidates(
    ont: Ontology,
    pattern: BasePattern,
    within: str | None,
) -> Iterator[tuple[str, str]]:
    """Stream candidate axioms from DB, narrowed by type and scope.

    Cursor-based iteration: caller may break early without buffering the full
    result set. Safe because `match_axioms` doesn't write during iteration.
    """
    joins: list[str] = []
    conditions: list[str] = []
    # JOIN params must appear before WHERE params in the final list because
    # SQLite binds positional `?` placeholders in SQL left-to-right, and JOIN
    # ON clauses precede WHERE in the generated statement.
    join_params: list[str] = []
    cond_params: list[str] = []

    if isinstance(pattern, _EXPRESSION_PATTERN_CLASSES):
        placeholders = ",".join("?" for _ in _EXPRESSION_CONTAINER_TYPES)
        conditions.append(f"a.type IN ({placeholders})")
        cond_params.extend(sorted(_EXPRESSION_CONTAINER_TYPES))
    else:
        conditions.append("a.type = ?")
        cond_params.append(pattern.axiom_tag())

    concrete_iris = _extract_concrete_iris(pattern)
    for iri in concrete_iris[:3]:
        alias = f"ae_p{len(joins)}"
        joins.append(
            f"JOIN axiom_entities {alias} ON {alias}.axiom_id = a.id AND {alias}.entity_iri = ?"
        )
        join_params.append(iri)

    if within is not None:
        sel = get_selection(ont, within)
        if sel.kind == SelectionKind.AXIOMS:
            joins.append(
                "JOIN selection_items si_w ON si_w.item = a.hash AND si_w.selection_name = ?"
            )
            join_params.append(within)
        else:
            joins.append("JOIN axiom_entities ae_w ON ae_w.axiom_id = a.id")
            joins.append(
                "JOIN selection_items si_w ON si_w.item = ae_w.entity_iri AND si_w.selection_name = ?"
            )
            join_params.append(within)

    join_clause = (" " + " ".join(joins)) if joins else ""
    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    # ORDER BY a.hash: candidate order determines which axioms hit the
    # match-and-limit cap; without it page-1 results drift across runs.
    yield from ont.conn.execute(
        f"SELECT DISTINCT a.hash, json(a.data) FROM axioms a{join_clause}{where_clause} "
        "ORDER BY a.hash",
        join_params + cond_params,
    )


def _extract_concrete_iris(pattern: BasePattern) -> list[str]:
    """Extract concrete IRI values from a pattern for index narrowing."""
    iris: list[str] = []
    _walk_for_iris(pattern, iris)
    return iris


def _walk_for_iris(obj: object, iris: list[str]):
    """Recursively collect concrete IRI values from a pattern object."""
    match obj:
        case IRI():
            iris.append(str(obj))
        case Slot() if obj.is_iri:
            iris.append(str(obj))
        case Slot():
            return
        case FrozenModel():
            for field_name in type(obj).model_fields:
                if field_name in SKIP:
                    continue
                _walk_for_iris(getattr(obj, field_name), iris)
        case tuple():
            for item in obj:
                _walk_for_iris(item, iris)
        case str() | int() | float() | None:
            return
        case _:
            msg = f"unhandled value {type(obj).__name__} in IRI walker"
            raise TypeError(msg)
