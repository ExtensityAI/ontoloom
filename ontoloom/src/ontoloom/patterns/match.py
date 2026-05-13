"""Pattern matcher: matches patterns against axioms, returns variable bindings."""

from __future__ import annotations

from collections.abc import Iterator
from itertools import permutations
from typing import get_args

from pydantic.fields import FieldInfo

from ontoloom.canonical import SKIP
from ontoloom.owl.axioms import BaseAxiom
from ontoloom.owl.expressions import BaseClassExpression
from ontoloom.owl.literals import LangLiteral, TypedLiteral
from ontoloom.owl.markers import is_unordered
from ontoloom.patterns.slot import BaseSlot, IRISlot, VariableSlot, WildcardSlot
from ontoloom.patterns.types import (
    BasePattern,
    ExpressionPattern,
    TupleMatch,
)

Bindings = dict[str, str]

_EXPRESSION_PATTERN_CLASSES: tuple[type, ...] = get_args(ExpressionPattern)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def match_pattern(pattern: BasePattern, axiom: BaseAxiom) -> list[Bindings]:
    """Match a pattern against an axiom.

    - Axiom-level pattern: matches the whole axiom. Returns 0 or 1 binding dicts.
    - Expression-level pattern: searches all sub-expressions. Returns 0+ binding dicts.
    """
    if isinstance(pattern, _EXPRESSION_PATTERN_CLASSES):
        results: list[Bindings] = []
        for expr in _iter_expressions(axiom):
            bindings = _match_model(pattern, expr, {})
            if bindings is not None:
                results.append(bindings)
        return results

    # Axiom-level pattern: type must match the axiom's type
    if pattern.axiom_tag() == axiom.tag():
        result = _match_model(pattern, axiom, {})
        return [result] if result is not None else []

    return []


# ---------------------------------------------------------------------------
# Model matching (recursive structural comparison)
# ---------------------------------------------------------------------------


def _match_model(
    pattern: BasePattern, actual: BaseAxiom | BaseClassExpression | str, bindings: Bindings
) -> Bindings | None:
    """Match a pattern model against an actual model, field by field."""
    # Handle bare IRI strings: match pattern.iri against the string
    if isinstance(actual, str):
        if hasattr(pattern, "iri") and isinstance(getattr(pattern, "iri", None), BaseSlot):
            return _match_slot_vs_str(pattern.iri, actual, bindings)  # pyright: ignore[reportAttributeAccessIssue]
        return None

    if pattern.axiom_tag() != actual.tag():
        return None

    actual_fields = type(actual).model_fields
    pattern_fields = type(pattern).model_fields
    for field_name in pattern_fields:
        if field_name in SKIP or field_name.endswith("_match"):
            continue

        pattern_val = getattr(pattern, field_name)
        actual_val = getattr(actual, field_name, None)
        if actual_val is None:
            return None

        # Pattern's sibling mode (codegen-emitted) drives tuple match semantics.
        mode = getattr(pattern, f"{field_name}_match", TupleMatch.EXACT)
        # Look up Unordered marker on the actual axiom's field -> pattern fields
        # don't carry the marker, the axiom side does.
        result = _match_field(
            pattern_val, actual_val, bindings, actual_fields.get(field_name), mode
        )
        if result is None:
            return None
        bindings = result

    return bindings


def _match_field(  # noqa: C901
    pattern_val: object,
    actual_val: object,
    bindings: Bindings,
    info: FieldInfo | None = None,
    mode: TupleMatch = TupleMatch.EXACT,
) -> Bindings | None:
    """Dispatch matching based on the pattern value's type."""
    # Slot against a class expression (shorthand semantics)
    if isinstance(pattern_val, BaseSlot) and isinstance(actual_val, BaseClassExpression):
        return _match_slot_vs_expression(pattern_val, actual_val, bindings)

    # Slot against a string (IRI or EntityType)
    if isinstance(pattern_val, BaseSlot) and isinstance(actual_val, str):
        return _match_slot_vs_str(pattern_val, str(actual_val), bindings)

    # Slot against a typed/lang literal: bind to the canonical string repr
    # (`"Dog"@en`, `"42"^^xsd:integer`) so cross-position equality holds and
    # different literal shapes don't unify spuriously.
    if isinstance(pattern_val, BaseSlot) and isinstance(actual_val, TypedLiteral | LangLiteral):
        return _match_slot_vs_str(pattern_val, str(actual_val), bindings)

    # Tuple match: ordered fields match positionally; unordered fields use the
    # `mode` from the pattern's sibling `<field>_match` enum.
    if isinstance(pattern_val, tuple) and isinstance(actual_val, tuple):
        if info is not None and is_unordered(info):
            if mode == TupleMatch.EXACT and len(pattern_val) != len(actual_val):
                return None
            return _match_contains(pattern_val, actual_val, bindings)
        return _match_tuple(pattern_val, actual_val, bindings)

    # Nested model (expression pattern vs expression).
    if isinstance(pattern_val, BasePattern):
        if isinstance(actual_val, BaseClassExpression):
            return _match_model(pattern_val, actual_val, bindings)
        if isinstance(actual_val, str):
            return _match_model(pattern_val, actual_val, bindings)

    # Concrete value equality (enums, literals)
    if pattern_val == actual_val:
        return bindings

    return None


# ---------------------------------------------------------------------------
# Slot matching
# ---------------------------------------------------------------------------


def _match_slot_vs_str(slot: BaseSlot, actual: str, bindings: Bindings) -> Bindings | None:
    """Match a Slot against a plain string (IRI field, EntityType, etc.)."""
    match slot:
        case WildcardSlot():
            return bindings
        case VariableSlot():
            return _bind_variable(slot.name, actual, bindings)
        case IRISlot():
            return bindings if slot == actual else None
        case _:
            msg = f"unhandled BaseSlot subtype {type(slot).__name__}"
            raise TypeError(msg)


def _match_slot_vs_expression(
    slot: BaseSlot,
    expr: str | BaseClassExpression,
    bindings: Bindings,
) -> Bindings | None:
    """Match a Slot against a ClassExpression or bare IRI string.

    Semantics:
    - Wildcard: matches any expression.
    - Variable: binds to the IRI string for bare IRI, else to repr.
    - Concrete IRI: matches a bare IRI string with the same value.
    """
    match slot:
        case WildcardSlot():
            return bindings
        case VariableSlot():
            return _bind_variable(
                slot.name, expr if isinstance(expr, str) else repr(expr), bindings
            )
        case IRISlot():
            return bindings if isinstance(expr, str) and slot == expr else None
        case _:
            msg = f"unhandled BaseSlot subtype {type(slot).__name__}"
            raise TypeError(msg)


def _bind_variable(name: str, value: str, bindings: Bindings) -> Bindings | None:
    """Bind a variable, checking consistency with existing bindings."""
    if name in bindings:
        return bindings if bindings[name] == value else None
    return {**bindings, name: value}


# ---------------------------------------------------------------------------
# Tuple and Contains matching
# ---------------------------------------------------------------------------


def _match_tuple(pattern_items: tuple, actual_items: tuple, bindings: Bindings) -> Bindings | None:
    """Exact list match: same length, each element matched in order."""
    if len(pattern_items) != len(actual_items):
        return None
    for p, a in zip(pattern_items, actual_items, strict=True):
        result = _match_field(p, a, bindings)
        if result is None:
            return None
        bindings = result
    return bindings


def _match_contains(
    pattern_items: tuple, actual_items: tuple, bindings: Bindings
) -> Bindings | None:
    """Partial list match: all pattern items must be found in actual (any order).

    Tries assignments of pattern items to actual items. For typical pattern
    sizes (1-3 items), this is fast.
    """
    if len(pattern_items) > len(actual_items):
        return None
    if len(pattern_items) == 0:
        return bindings

    for indices in permutations(range(len(actual_items)), len(pattern_items)):
        trial_bindings = dict(bindings)
        matched = True
        for pi, ai in enumerate(indices):
            result = _match_field(pattern_items[pi], actual_items[ai], trial_bindings)
            if result is None:
                matched = False
                break
            trial_bindings = result
        if matched:
            return trial_bindings

    return None


# ---------------------------------------------------------------------------
# Expression tree traversal
# ---------------------------------------------------------------------------


def _iter_expressions(obj: BaseAxiom | BaseClassExpression) -> Iterator[BaseClassExpression | str]:
    """Recursively yield all ClassExpression nodes within an axiom or expression."""
    for field_name in type(obj).model_fields:
        if field_name in SKIP:
            continue
        val = getattr(obj, field_name)
        yield from _iter_field_expressions(val)


def _iter_field_expressions(val: object) -> Iterator[BaseClassExpression | str]:
    """Yield expressions from a single field value."""
    if isinstance(val, BaseClassExpression):
        yield val
        # Recurse into the expression's own fields
        yield from _iter_expressions(val)
    elif isinstance(val, str):
        # Bare IRI (subclass of str)
        yield val
    elif isinstance(val, tuple):
        for item in val:
            if isinstance(item, BaseClassExpression):
                yield item
                yield from _iter_expressions(item)
            elif isinstance(item, str):
                # Bare IRI in tuple
                yield item
