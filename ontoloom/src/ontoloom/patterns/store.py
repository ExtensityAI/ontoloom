"""Search axioms using pattern matching, integrated with DB and selections."""

from __future__ import annotations

import typing
from collections.abc import Iterator
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Annotated, get_args, get_origin

from ontoloom.axioms.deserialize import load_axiom
from ontoloom.axioms.hashing import AxiomHash, short_hash
from ontoloom.connection import Session
from ontoloom.models import FrozenModel
from ontoloom.owl.axioms import AXIOM_CLASSES, AxiomTag
from ontoloom.owl.expressions import ClassExpression
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import SKIP
from ontoloom.patterns.match import match_pattern
from ontoloom.patterns.slot import IRISlot, VariableSlot, WildcardSlot
from ontoloom.patterns.types import BasePattern, ExpressionPattern
from ontoloom.query.constraints import (
    AxiomConstraint,
    InSelection,
    MentionsAll,
    WithTypes,
)
from ontoloom.query.dispatch import run
from ontoloom.query.stream_axioms import StreamAxioms
from ontoloom.selections.types import SelectionRef


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Result of a pattern match search.

    `truncated=True` means iteration stopped at `limit`; more matches may exist.
    """

    axiom_hashes: tuple[AxiomHash, ...]
    truncated: bool = False


def match_axioms(
    s: Session,
    pattern: BasePattern,
    *,
    within: SelectionRef | None = None,
    limit: int | None = None,
) -> MatchResult:
    """Find axioms matching a pattern. Returns matched hashes.

    For axiom-level patterns, filters candidates by axiom type.
    For expression-level patterns, searches all axioms (or scoped set).
    `limit` caps the number of matches collected; iteration stops early when hit.
    """
    matched_hashes: list[AxiomHash] = []
    truncated = False

    with _iter_candidates(s, pattern, within) as rows:
        for h, json_data in rows:
            axiom = load_axiom(json_data, f"match {short_hash(h)}")
            if match_pattern(pattern, axiom):
                matched_hashes.append(AxiomHash(h))
                if limit is not None and len(matched_hashes) >= limit:
                    truncated = True
                    break

    return MatchResult(
        axiom_hashes=tuple(matched_hashes),
        truncated=truncated,
    )


_EXPRESSION_PATTERN_CLASSES: tuple[type, ...] = get_args(ExpressionPattern)

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


_EXPRESSION_CONTAINER_TYPES: tuple[AxiomTag, ...] = tuple(
    AxiomTag(cls.__name__) for cls in AXIOM_CLASSES if _has_class_expression_field(cls)
)


def _iter_candidates(
    s: Session,
    pattern: BasePattern,
    within: SelectionRef | None,
) -> AbstractContextManager[Iterator[tuple[AxiomHash, str]]]:
    """Stream candidate axioms from DB, narrowed by type and scope.

    Cursor-based iteration: caller may break early without buffering the full
    result set. Safe because `match_axioms` doesn't write during iteration.
    """
    constraints: list[AxiomConstraint] = []

    if isinstance(pattern, _EXPRESSION_PATTERN_CLASSES):
        constraints.append(WithTypes(tags=tuple(sorted(_EXPRESSION_CONTAINER_TYPES))))
    else:
        constraints.append(WithTypes(tags=(AxiomTag(pattern.axiom_tag()),)))

    concrete_iris = _extract_concrete_iris(pattern)
    if concrete_iris[:3]:
        constraints.append(MentionsAll(iris=tuple(IRI(iri) for iri in concrete_iris[:3])))

    if within is not None:
        constraints.append(InSelection(ref=within))

    return run(s, StreamAxioms(constraints=tuple(constraints)))


def _extract_concrete_iris(pattern: BasePattern) -> list[str]:
    """Extract concrete IRI values from a pattern for index narrowing."""
    iris: list[str] = []
    _walk_for_iris(pattern, iris)
    return iris


def _walk_for_iris(obj: object, iris: list[str]):
    """Recursively collect concrete IRI values from a pattern object."""
    match obj:
        case IRISlot():
            iris.append(str(obj))
        case WildcardSlot() | VariableSlot():
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
