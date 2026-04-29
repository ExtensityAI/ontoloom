"""Pattern matcher: matches patterns against axioms, returns variable bindings."""

from __future__ import annotations

from collections.abc import Iterator
from itertools import permutations
from typing import get_args

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from ontoloom.ontology.models.base import BaseAxiom, BaseClassExpression
from ontoloom.ontology.models.expressions import NamedClass
from ontoloom.ontology.models.markers import is_unordered
from ontoloom.ontology.patterns import Contains, ExpressionPattern, Pattern
from ontoloom.ontology.patterns.slot import Slot

Bindings = dict[str, str]

_EXPRESSION_PATTERN_CLASSES: tuple[type, ...] = get_args(ExpressionPattern)


def _axiom_type_for_pattern(pattern_type: str):
    """Strip 'Pattern' suffix to get the corresponding axiom/expression type name."""
    if pattern_type.endswith("Pattern"):
        return pattern_type[: -len("Pattern")]
    return pattern_type


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def match_pattern(pattern: Pattern, axiom: BaseAxiom) -> list[Bindings]:
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
    pattern_type: str = pattern.type  # pyright: ignore[reportAttributeAccessIssue]
    if _axiom_type_for_pattern(pattern_type) == axiom.type:
        result = _match_model(pattern, axiom, {})
        return [result] if result is not None else []

    return []


# ---------------------------------------------------------------------------
# Model matching (recursive structural comparison)
# ---------------------------------------------------------------------------


def _match_model(pattern: BaseModel, actual: BaseModel, bindings: Bindings) -> Bindings | None:
    """Match a pattern model against an actual model, field by field."""
    pattern_type = getattr(pattern, "type", None)
    actual_type = getattr(actual, "type", None)

    if pattern_type and actual_type and _axiom_type_for_pattern(pattern_type) != actual_type:
        return None

    actual_fields = type(actual).model_fields
    for field_name in type(pattern).model_fields:
        if field_name in ("type", "annotations"):
            continue

        pattern_val = getattr(pattern, field_name)
        actual_val = getattr(actual, field_name, None)
        if actual_val is None:
            return None

        # Look up Unordered marker on the actual axiom's field — pattern fields
        # don't carry the marker, the axiom side does.
        result = _match_field(pattern_val, actual_val, bindings, actual_fields.get(field_name))
        if result is None:
            return None
        bindings = result

    return bindings


def _match_field(
    pattern_val: object,
    actual_val: object,
    bindings: Bindings,
    info: FieldInfo | None = None,
) -> Bindings | None:
    """Dispatch matching based on the pattern value's type."""
    # Slot against a class expression (shorthand semantics)
    if isinstance(pattern_val, Slot) and isinstance(actual_val, BaseClassExpression):
        return _match_slot_vs_expression(pattern_val, actual_val, bindings)

    # Slot against a string (IRI or EntityType)
    if isinstance(pattern_val, Slot) and isinstance(actual_val, str):
        return _match_slot_vs_str(pattern_val, str(actual_val), bindings)

    # Contains: partial-set match (any subset, any order)
    if isinstance(pattern_val, Contains) and isinstance(actual_val, tuple):
        return _match_contains(pattern_val.contains, actual_val, bindings)

    # Plain tuple: dispatch on field metadata. Unordered fields require equal
    # length but allow any permutation; ordered fields require exact pairing.
    if isinstance(pattern_val, tuple) and isinstance(actual_val, tuple):
        if info is not None and is_unordered(info):
            if len(pattern_val) != len(actual_val):
                return None
            return _match_contains(pattern_val, actual_val, bindings)
        return _match_tuple(pattern_val, actual_val, bindings)

    # Nested model (expression pattern vs expression)
    if isinstance(pattern_val, BaseModel) and isinstance(actual_val, BaseModel):
        return _match_model(pattern_val, actual_val, bindings)

    # Concrete value equality (enums, literals)
    if pattern_val == actual_val:
        return bindings

    return None


# ---------------------------------------------------------------------------
# Slot matching
# ---------------------------------------------------------------------------


def _match_slot_vs_str(slot: Slot, actual: str, bindings: Bindings) -> Bindings | None:
    """Match a Slot against a plain string (IRI field, EntityType, etc.)."""
    if slot.is_wildcard:
        return bindings
    if slot.is_variable:
        return _bind_variable(slot.var_name, actual, bindings)
    # Concrete IRI: exact string match
    return bindings if str(slot) == actual else None


def _match_slot_vs_expression(
    slot: Slot, expr: BaseClassExpression, bindings: Bindings
) -> Bindings | None:
    """Match a Slot against a ClassExpression.

    Semantics:
    - Wildcard: matches any expression.
    - Variable: binds to the IRI if expr is NamedClass, else to repr.
    - Concrete IRI: shorthand for NamedClass(iri=X). Only matches NamedClass.
    """
    if slot.is_wildcard:
        return bindings

    if slot.is_variable:
        bound_value = str(expr.iri) if isinstance(expr, NamedClass) else repr(expr)
        return _bind_variable(slot.var_name, bound_value, bindings)

    # Concrete IRI: only matches NamedClass with same IRI
    if isinstance(expr, NamedClass) and str(expr.iri) == str(slot):
        return bindings
    return None


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


def _iter_expressions(obj: BaseModel) -> Iterator[BaseClassExpression]:
    """Recursively yield all ClassExpression nodes within an axiom or expression."""
    for field_name in type(obj).model_fields:
        if field_name in ("type", "annotations"):
            continue
        val = getattr(obj, field_name)
        yield from _iter_field_expressions(val)


def _iter_field_expressions(val: object) -> Iterator[BaseClassExpression]:
    """Yield expressions from a single field value."""
    if isinstance(val, BaseClassExpression):
        yield val
        # Recurse into the expression's own fields
        yield from _iter_expressions(val)
    elif isinstance(val, tuple):
        for item in val:
            if isinstance(item, BaseClassExpression):
                yield item
                yield from _iter_expressions(item)
