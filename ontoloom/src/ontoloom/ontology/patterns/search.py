"""Search axioms using pattern matching, integrated with DB and selections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import get_args

from ontoloom.ontology import selections
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.load import load_axiom
from ontoloom.ontology.patterns import ExpressionPattern, Pattern
from ontoloom.ontology.patterns.match import match_pattern
from ontoloom.ontology.patterns.slot import Slot
from ontoloom.ontology.types import SelectionKind


@dataclass
class MatchResult:
    """Result of a pattern match search."""

    axiom_hashes: list[str]
    total: int


def match_axioms(
    ont: Ontology,
    pattern: Pattern,
    *,
    within: str | None = None,
) -> MatchResult:
    """Find axioms matching a pattern. Returns matched hashes.

    For axiom-level patterns, filters candidates by axiom type.
    For expression-level patterns, searches all axioms (or scoped set).
    """
    candidates = _fetch_candidates(ont, pattern, within)
    matched_hashes: list[str] = []
    for h, json_data in candidates:
        axiom = load_axiom(json_data, f"match {h[:8]}")
        if match_pattern(pattern, axiom):
            matched_hashes.append(h)
    return MatchResult(axiom_hashes=matched_hashes, total=len(matched_hashes))


_EXPRESSION_PATTERN_CLASSES: tuple[type, ...] = get_args(ExpressionPattern)

# TODO: this list duplicates structural knowledge already in the axiom hierarchy.
# Considered: ClassVar on each class set via __pydantic_init_subclass__, adding a
# DB column, or dropping the filter (small perf cost on wildcard expression
# patterns). None felt clean enough yet — revisit when the implementation lands
# and we can measure the actual cost of dropping it.
_EXPRESSION_CONTAINER_TYPES = frozenset(
    [
        "SubClassOf",
        "EquivalentClasses",
        "DisjointClasses",
        "ObjectPropertyDomain",
        "ObjectPropertyRange",
        "DataPropertyDomain",
        "ClassAssertion",
        "HasKey",
    ]
)


def _fetch_candidates(
    ont: Ontology,
    pattern: Pattern,
    within: str | None,
) -> list[tuple[str, str]]:
    """Fetch candidate axioms from DB, narrowed by type and scope."""
    joins: list[str] = []
    conditions: list[str] = []
    params: list[str | int] = []

    if isinstance(pattern, _EXPRESSION_PATTERN_CLASSES):
        # Expression-level: search axioms that can contain class expressions
        placeholders = ",".join("?" for _ in _EXPRESSION_CONTAINER_TYPES)
        conditions.append(f"a.type IN ({placeholders})")
        params.extend(sorted(_EXPRESSION_CONTAINER_TYPES))
    else:
        # Axiom-level: exact type match — strip "Pattern" suffix from the discriminator
        pattern_type: str = pattern.type  # pyright: ignore[reportAttributeAccessIssue]
        conditions.append("a.type = ?")
        params.append(pattern_type.removesuffix("Pattern"))

    # Narrow by concrete IRIs in the pattern (index acceleration)
    concrete_iris = _extract_concrete_iris(pattern)
    for iri in concrete_iris[:3]:  # limit to 3 joins for performance
        joins.append(
            f"JOIN axiom_entities ae_p{len(joins)} "
            f"ON ae_p{len(joins)}.axiom_id = a.id AND ae_p{len(joins)}.entity_iri = ?"
        )
        params.append(iri)

    # Scope to selection
    if within is not None:
        sel = selections.get_info(ont, within)
        if sel.kind == SelectionKind.AXIOMS:
            joins.append(
                "JOIN selection_items si_w ON si_w.item = a.hash AND si_w.selection_name = ?"
            )
            params.append(within)
        else:  # entities
            joins.append("JOIN axiom_entities ae_w ON ae_w.axiom_id = a.id")
            joins.append(
                "JOIN selection_items si_w ON si_w.item = ae_w.entity_iri AND si_w.selection_name = ?"
            )
            params.append(within)

    join_clause = (" " + " ".join(joins)) if joins else ""
    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    return ont.conn.execute(
        f"SELECT DISTINCT a.hash, json(a.data) FROM axioms a{join_clause}{where_clause}",
        params,
    ).fetchall()


def _extract_concrete_iris(pattern: Pattern) -> list[str]:
    """Extract concrete IRI values from a pattern for index narrowing."""
    iris: list[str] = []
    _walk_for_iris(pattern, iris)
    return iris


def _walk_for_iris(obj: object, iris: list[str]) -> None:
    """Recursively collect concrete IRI Slots from a pattern object."""
    if isinstance(obj, Slot) and obj.is_iri:
        iris.append(str(obj))
    elif hasattr(type(obj), "model_fields"):
        for field_name in type(obj).model_fields:  # pyright: ignore[reportAttributeAccessIssue]
            if field_name == "type":
                continue
            val = getattr(obj, field_name)
            _walk_for_iris(val, iris)
    elif isinstance(obj, tuple):
        for item in obj:
            _walk_for_iris(item, iris)
