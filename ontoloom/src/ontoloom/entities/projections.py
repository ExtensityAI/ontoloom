"""Bespoke entity-keyed projections over `entity_text` and `axiom_entities`.

These reads are deliberately not in the DSL — they project from a third table
(`entity_text`) or hand-roll ranked text-search predicates the DSL does not
model. Adding them to the query DSL would extend the predicate dispatcher to
configurable column aliases and a new projection tier for a small number of
call sites. The bespoke-aggregation allowlist in CLAUDE.md covers this surface
alongside `prefix_usage_counts` and `top_entities_by_axiom_count`.
"""

from collections.abc import Sequence

from ontoloom.connection import Session
from ontoloom.entities.text import LOCAL_NAME_PROPERTY
from ontoloom.entities.types import (
    AnnotationRow,
    EntityDisplay,
    MatchQuality,
    MatchSource,
    TextMatch,
)
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType

_TEXT_SCAN_CAP = 1000


def find_text_matches(
    s: Session,
    query: str,
    property_filter: str | None,
    source_label: MatchSource,
    *,
    properties: Sequence[IRI] = (),
) -> dict[str, TextMatch]:
    """Returns {iri: TextMatch}.

    properties: when non-empty, restrict annotation search to these property IRIs.
    Only applies when property_filter is None (annotation search path).
    """
    params: list[str] = []
    if property_filter is not None:
        prop_cond = "property = ?"
        params.append(property_filter)
    elif properties:
        ph = ",".join("?" for _ in properties)
        prop_cond = f"property IN ({ph})"
        params.extend(properties)
    else:
        prop_cond = "property != ?"
        params.append(LOCAL_NAME_PROPERTY)

    # ORDER BY entity_iri: insertion order determines `_text_search_entities`
    # pagination output. Without it, page-1 contents drift across runs.
    # LIMIT _TEXT_SCAN_CAP: bound memory for runaway substring queries; user
    # sees first-N alphabetical IRIs rather than all matches.
    matches: dict[str, TextMatch] = {}
    query_lower = query.lower()

    for (iri_str,) in s.conn.execute(
        f"SELECT DISTINCT entity_iri FROM entity_text WHERE {prop_cond} AND LOWER(text) = ? ORDER BY entity_iri LIMIT ?",
        [*params, query_lower, _TEXT_SCAN_CAP],
    ):
        if iri_str not in matches:
            matches[iri_str] = TextMatch(source_label, MatchQuality.EXACT)

    for (iri_str,) in s.conn.execute(
        f"SELECT DISTINCT entity_iri FROM entity_text WHERE {prop_cond} AND INSTR(LOWER(text), ?) > 0 ORDER BY entity_iri LIMIT ?",
        [*params, query_lower, _TEXT_SCAN_CAP],
    ):
        if iri_str not in matches:
            matches[iri_str] = TextMatch(source_label, MatchQuality.SUBSTRING)

    return matches


def batch_fetch_entity_display(s: Session, iris: list[str]) -> dict[str, EntityDisplay]:
    placeholders = ",".join("?" for _ in iris)

    roles_by_iri: dict[str, set[EntityType]] = {}
    for iri_str, role_val in s.conn.execute(
        f"SELECT entity_iri, role FROM axiom_entities WHERE entity_iri IN ({placeholders}) AND role IS NOT NULL",
        iris,
    ):
        roles_by_iri.setdefault(iri_str, set()).add(EntityType(role_val))

    anns_by_iri: dict[str, list[AnnotationRow]] = {}
    for iri_str, prop, text in s.conn.execute(
        f"SELECT DISTINCT entity_iri, property, text FROM entity_text "
        f"WHERE entity_iri IN ({placeholders}) AND property != ? "
        f"ORDER BY entity_iri, property, text",
        [*iris, LOCAL_NAME_PROPERTY],
    ):
        anns_by_iri.setdefault(iri_str, []).append(AnnotationRow(property=IRI(prop), value=text))

    return {
        iri_str: EntityDisplay(
            roles=frozenset(roles_by_iri.get(iri_str, ())),
            annotations=tuple(anns_by_iri.get(iri_str, ())),
        )
        for iri_str in iris
    }


def top_entities_by_axiom_count(s: Session, n: int) -> list[tuple[IRI, int]]:
    """Top n entities by number of distinct axioms they appear in."""
    return [
        (IRI(row[0]), row[1])
        for row in s.conn.execute(
            "SELECT ae.entity_iri, COUNT(DISTINCT ae.axiom_id) AS cnt "
            "FROM axiom_entities ae "
            "GROUP BY ae.entity_iri "
            "ORDER BY cnt DESC "
            "LIMIT ?",
            (n,),
        ).fetchall()
    ]
