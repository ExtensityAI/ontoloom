"""Search axioms using pattern matching, integrated with DB and selections."""

from __future__ import annotations

from dataclasses import dataclass

from ontoloom.ontology import selections
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.load import load_axiom
from ontoloom.ontology.patterns.match import match_pattern
from ontoloom.ontology.patterns.models import Pattern, Slot
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
    pattern_type: str = pattern.type  # pyright: ignore[reportAttributeAccessIssue]
    axiom_type = _axiom_type_for_pattern(pattern_type)

    # Build candidate query
    candidates = _fetch_candidates(ont, axiom_type, pattern, within)

    matched_hashes: list[str] = []

    for h, json_data in candidates:
        axiom = load_axiom(json_data, f"match {h[:8]}")
        if match_pattern(pattern, axiom):
            matched_hashes.append(h)

    return MatchResult(axiom_hashes=matched_hashes, total=len(matched_hashes))


def _axiom_type_for_pattern(pattern_type: str):
    if pattern_type.endswith("Pattern"):
        return pattern_type[: -len("Pattern")]
    return pattern_type


_EXPRESSION_TYPE_NAMES = frozenset(
    [
        "NamedClass",
        "ObjectSomeValuesFrom",
        "ObjectIntersectionOf",
        "ObjectOneOf",
        "ObjectHasValue",
        "ObjectHasSelf",
        "DataSomeValuesFrom",
        "DataHasValue",
    ]
)

# Maps expression types to axiom types that can contain them
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
    axiom_type: str,
    pattern: Pattern,
    within: str | None,
) -> list[tuple[str, str]]:
    """Fetch candidate axioms from DB, narrowed by type and scope."""
    joins: list[str] = []
    conditions: list[str] = []
    params: list[str | int] = []

    # Type filter
    if axiom_type in _EXPRESSION_TYPE_NAMES:
        # Expression-level: search axioms that can contain class expressions
        placeholders = ",".join("?" for _ in _EXPRESSION_CONTAINER_TYPES)
        conditions.append(f"a.type IN ({placeholders})")
        params.extend(sorted(_EXPRESSION_CONTAINER_TYPES))
    else:
        # Axiom-level: exact type match
        conditions.append("a.type = ?")
        params.append(axiom_type)

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
    elif hasattr(obj, "model_fields"):
        for field_name in obj.model_fields:  # pyright: ignore[reportAttributeAccessIssue]
            if field_name == "type":
                continue
            val = getattr(obj, field_name)
            _walk_for_iris(val, iris)
    elif isinstance(obj, tuple):
        for item in obj:
            _walk_for_iris(item, iris)
