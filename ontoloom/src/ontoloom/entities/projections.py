"""Bespoke entity-keyed projections over `entity_text` and `axiom_entities`.

These reads are deliberately not in the DSL — they project from a third table
(`entity_text`) that the DSL does not model. Adding them to the query DSL would
extend the predicate dispatcher to configurable column aliases and a new
projection tier for a small number of call sites. The bespoke-aggregation
allowlist in CLAUDE.md covers this surface alongside `count_prefix_usage` and
`find_top_entities_by_axiom_count`.
"""

from ontoloom.connection import Session
from ontoloom.entities.text import LOCAL_NAME_PROPERTY
from ontoloom.entities.types import (
    AnnotationRow,
    EntityDisplay,
)
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query.constraints import InAxiomSelection, InEntitySelection


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


def find_top_entities_by_axiom_count(
    s: Session,
    n: int,
    *,
    within: InAxiomSelection | InEntitySelection | None = None,
) -> list[tuple[IRI, int]]:
    """Top n entities by number of distinct axioms they appear in.

    Scoping:
    - within=None: all axioms.
    - within=InAxiomSelection: count only axioms in that selection.
    - within=InEntitySelection: restrict to entities in that selection (count
      stays each entity's full appearance count across the ontology).
    """
    match within:
        case None:
            sql = (
                "SELECT ae.entity_iri, COUNT(DISTINCT ae.axiom_id) AS cnt "
                "FROM axiom_entities ae "
                "GROUP BY ae.entity_iri ORDER BY cnt DESC LIMIT ?"
            )
            params: tuple[object, ...] = (n,)
        case InAxiomSelection(name=ax_name):
            sql = (
                "SELECT ae.entity_iri, COUNT(DISTINCT ae.axiom_id) AS cnt "
                "FROM axiom_entities ae "
                "JOIN axioms a ON a.id = ae.axiom_id "
                "JOIN axiom_selection_items asi "
                "  ON asi.item = a.hash AND asi.selection_name = ? "
                "GROUP BY ae.entity_iri ORDER BY cnt DESC LIMIT ?"
            )
            params = (ax_name, n)
        case InEntitySelection(name=en_name):
            sql = (
                "SELECT ae.entity_iri, COUNT(DISTINCT ae.axiom_id) AS cnt "
                "FROM axiom_entities ae "
                "JOIN entity_selection_items esi "
                "  ON esi.item = ae.entity_iri AND esi.selection_name = ? "
                "GROUP BY ae.entity_iri ORDER BY cnt DESC LIMIT ?"
            )
            params = (en_name, n)
        case _:
            msg = f"unhandled within constraint: {within!r}"
            raise ValueError(msg)

    return [(IRI(row[0]), row[1]) for row in s.conn.execute(sql, params).fetchall()]
