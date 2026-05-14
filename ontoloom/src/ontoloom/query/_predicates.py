"""SQL fragment helpers and CompiledSql — pure outputs, no DB access."""

from collections.abc import Sequence
from dataclasses import dataclass

from ontoloom.connection import escape_like
from ontoloom.query._constraints import (
    AlwaysFalse,
    AxiomConstraint,
    Declared,
    EntityConstraint,
    HasEntityRole,
    InNamespaces,
    InPositions,
    InSelection,
    MentionedInAxioms,
    MentionsAll,
    MentionsAny,
    NotDeprecated,
    OfTypes,
    WithAnyProperty,
    WithIRIs,
    WithRoles,
)
from ontoloom.selections.types import SelectionKind
from ontoloom.text_index import DECLARED_EXISTS, DECLARED_NOT_EXISTS, NOT_DEPRECATED


@dataclass(frozen=True, slots=True)
class CompiledSql:
    sql: str
    params: tuple[object, ...]


def _entity_predicates(constraints: Sequence[EntityConstraint]) -> tuple[str, list[object]]:  # noqa: C901
    """Compile entity-domain constraints into an AND-joined SQL predicate.

    Returns `("1", [])` for no constraints and `("0", [])` when any
    `AlwaysFalse` is present. Otherwise returns the conjunction of
    per-constraint fragments plus their bind parameters.
    """
    if not constraints:
        return ("1", [])

    fragments: list[str] = []
    params: list[object] = []

    for c in constraints:
        if isinstance(c, AlwaysFalse):
            return ("0", [])

        if isinstance(c, WithIRIs):
            placeholders = ",".join("?" for _ in c.iris)
            fragments.append(f"ae.entity_iri IN ({placeholders})")
            params.extend(c.iris)
        elif isinstance(c, WithRoles):
            placeholders = ",".join("?" for _ in c.roles)
            fragments.append(f"ae.role IN ({placeholders})")
            params.extend(c.roles)
        elif isinstance(c, HasEntityRole):
            fragments.append("ae.role IS NOT NULL")
        elif isinstance(c, InNamespaces):
            ns_terms = [r"ae.entity_iri LIKE ? || ':%' ESCAPE '\'" for _ in c.namespaces]

            if len(ns_terms) == 1:
                fragments.append(ns_terms[0])
            else:
                fragments.append("(" + " OR ".join(ns_terms) + ")")

            params.extend(escape_like(ns) for ns in c.namespaces)
        elif isinstance(c, Declared):
            fragments.append(DECLARED_EXISTS if c.state else DECLARED_NOT_EXISTS)
        elif isinstance(c, NotDeprecated):
            fragments.append(NOT_DEPRECATED)
        elif isinstance(c, WithAnyProperty):
            placeholders = ",".join("?" for _ in c.properties)
            fragments.append(
                "EXISTS (SELECT 1 FROM entity_text et_p "
                "WHERE et_p.entity_iri = ae.entity_iri "
                f"AND et_p.property IN ({placeholders}))"
            )
            params.extend(c.properties)
        elif isinstance(c, MentionedInAxioms):
            placeholders = ",".join("?" for _ in c.hashes)
            fragments.append(
                "EXISTS (SELECT 1 FROM axioms a_m "
                "WHERE a_m.id = ae.axiom_id "
                f"AND a_m.hash IN ({placeholders}))"
            )
            params.extend(c.hashes)
        elif isinstance(c, InPositions):
            placeholders = ",".join("?" for _ in c.positions)
            fragments.append(f"ae.position IN ({placeholders})")
            params.extend(c.positions)
        elif isinstance(c, InSelection):
            if c.ref.kind == SelectionKind.ENTITIES:
                fragments.append(
                    "EXISTS (SELECT 1 FROM selection_items si_w "
                    "WHERE si_w.item = ae.entity_iri "
                    "AND si_w.selection_name = ?)"
                )
            else:
                fragments.append(
                    "EXISTS (SELECT 1 FROM selection_items si_w "
                    "JOIN axioms a_w ON a_w.hash = si_w.item "
                    "WHERE a_w.id = ae.axiom_id "
                    "AND si_w.selection_name = ?)"
                )

            params.append(c.ref.bare_name)
        else:
            msg = f"unknown entity constraint variant: {type(c).__name__}"
            raise ValueError(msg)

    return (" AND ".join(fragments), params)


def _axiom_predicates(constraints: Sequence[AxiomConstraint]) -> tuple[str, list[object]]:
    """Compile axiom-domain constraints into an AND-joined SQL predicate.

    Returns `("1", [])` for no constraints and `("0", [])` when any
    `AlwaysFalse` is present. Otherwise returns the conjunction of
    per-constraint fragments plus their bind parameters.
    """
    if not constraints:
        return ("1", [])

    fragments: list[str] = []
    params: list[object] = []

    for c in constraints:
        if isinstance(c, AlwaysFalse):
            return ("0", [])

        if isinstance(c, OfTypes):
            placeholders = ",".join("?" for _ in c.tags)
            fragments.append(f"a.type IN ({placeholders})")
            params.extend(c.tags)
        elif isinstance(c, MentionsAll):
            for iri in c.iris:
                fragments.append(
                    "EXISTS (SELECT 1 FROM axiom_entities ae_m "
                    "WHERE ae_m.axiom_id = a.id "
                    "AND ae_m.entity_iri = ?)"
                )
                params.append(iri)
        elif isinstance(c, MentionsAny):
            placeholders = ",".join("?" for _ in c.iris)
            fragments.append(
                "EXISTS (SELECT 1 FROM axiom_entities ae_m "
                "WHERE ae_m.axiom_id = a.id "
                f"AND ae_m.entity_iri IN ({placeholders}))"
            )
            params.extend(c.iris)
        elif isinstance(c, InSelection):
            if c.ref.kind == SelectionKind.AXIOMS:
                fragments.append(
                    "EXISTS (SELECT 1 FROM selection_items si_w "
                    "WHERE si_w.item = a.hash "
                    "AND si_w.selection_name = ?)"
                )
            else:
                fragments.append(
                    "EXISTS (SELECT 1 FROM axiom_entities ae_w "
                    "WHERE ae_w.axiom_id = a.id "
                    "AND EXISTS (SELECT 1 FROM selection_items si_w "
                    "WHERE si_w.item = ae_w.entity_iri "
                    "AND si_w.selection_name = ?))"
                )

            params.append(c.ref.bare_name)
        else:
            msg = f"unknown axiom constraint variant: {type(c).__name__}"
            raise ValueError(msg)

    return (" AND ".join(fragments), params)
