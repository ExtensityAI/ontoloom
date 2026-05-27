"""Predicate dispatchers and SQL fragments — internal to the query DSL.

All emitted fragments reference the bind-aliases `ae` (axiom_entities)
and `a` (axioms). Per-query render functions must use these aliases.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from ontoloom.entities.text import OWL_DEPRECATED_PROPERTY
from ontoloom.owl.axioms import Declaration
from ontoloom.query.constraints import (
    AxiomConstraint,
    Declared,
    Deprecated,
    EntityConstraint,
    HasAnyAnnotation,
    HasAnyProperty,
    HasRole,
    InAxiomSelection,
    InEntitySelection,
    InIRIs,
    InNamespaces,
    InPositions,
    MentionedIn,
    MentionsAll,
    MentionsAny,
    WithRoles,
    WithTypes,
)

# Backslash chosen as the LIKE-ESCAPE character; pair every use with `ESCAPE '\\'`.
LIKE_ESCAPE = "\\"


def escape_like(value: str):
    """Escape SQL LIKE metacharacters (`\\`, `%`, `_`) so a parameter is matched literally.
    Use with `LIKE ? ESCAPE '\\'`.
    """
    return (
        value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )


DECLARED_EXISTS = (
    "EXISTS (SELECT 1 FROM axiom_entities ae_d "
    "JOIN axioms a_d ON a_d.id = ae_d.axiom_id "
    f"WHERE ae_d.entity_iri = ae.entity_iri AND a_d.type = '{Declaration.tag()}')"
)
DECLARED_NOT_EXISTS = (
    "NOT EXISTS (SELECT 1 FROM axiom_entities ae_d "
    "JOIN axioms a_d ON a_d.id = ae_d.axiom_id "
    f"WHERE ae_d.entity_iri = ae.entity_iri AND a_d.type = '{Declaration.tag()}')"
)
NOT_DEPRECATED = (
    "NOT EXISTS (SELECT 1 FROM entity_text et_dep "
    "WHERE et_dep.entity_iri = ae.entity_iri "
    "AND et_dep.property = ? AND LOWER(et_dep.text) = 'true')"
)


@dataclass(frozen=True, slots=True)
class Predicate:
    """An AND-joined SQL fragment with bind params.

    `sql == "1"` is the tautology produced when no constraints are present
    (caller emits `WHERE 1`; SQLite folds this away). Callers always embed
    `pred.sql` literally; no special-case inspection of this value is needed.
    """

    sql: str
    params: tuple[object, ...]


def _entity_predicates(constraints: Sequence[EntityConstraint]) -> Predicate:  # noqa: C901
    if not constraints:
        return Predicate(sql="1", params=())

    fragments: list[str] = []
    params: list[object] = []

    for c in constraints:
        match c:
            case InIRIs(iris=iris):
                placeholders = ",".join("?" for _ in iris)
                fragments.append(f"ae.entity_iri IN ({placeholders})")
                params.extend(iris)
            case WithRoles(roles=roles):
                placeholders = ",".join("?" for _ in roles)
                fragments.append(f"ae.role IN ({placeholders})")
                params.extend(roles)
            case HasRole():
                fragments.append("ae.role IS NOT NULL")
            case InNamespaces(namespaces=namespaces):
                ns_terms = [r"ae.entity_iri LIKE ? || ':%' ESCAPE '\'" for _ in namespaces]

                if len(ns_terms) == 1:
                    fragments.append(ns_terms[0])
                else:
                    fragments.append("(" + " OR ".join(ns_terms) + ")")

                params.extend(escape_like(ns) for ns in namespaces)
            case Declared(state=state):
                fragments.append(DECLARED_EXISTS if state else DECLARED_NOT_EXISTS)
            case Deprecated(state=False):
                fragments.append(NOT_DEPRECATED)
                params.append(OWL_DEPRECATED_PROPERTY)
            case HasAnyProperty(properties=properties):
                placeholders = ",".join("?" for _ in properties)
                fragments.append(
                    "EXISTS (SELECT 1 FROM entity_text et_p "
                    "WHERE et_p.entity_iri = ae.entity_iri "
                    f"AND et_p.property IN ({placeholders}))"
                )
                params.extend(properties)
            case MentionedIn(hashes=hashes):
                placeholders = ",".join("?" for _ in hashes)
                fragments.append(
                    "EXISTS (SELECT 1 FROM axioms a_m "
                    "WHERE a_m.id = ae.axiom_id "
                    f"AND a_m.hash IN ({placeholders}))"
                )
                params.extend(hashes)
            case InPositions(positions=positions):
                placeholders = ",".join("?" for _ in positions)
                fragments.append(f"ae.position IN ({placeholders})")
                params.extend(positions)
            case InEntitySelection(name=name):
                fragments.append(
                    "EXISTS (SELECT 1 FROM entity_selection_items si_w "
                    "WHERE si_w.item = ae.entity_iri "
                    "AND si_w.selection_name = ?)"
                )
                params.append(name)
            case InAxiomSelection(name=name):
                fragments.append(
                    "EXISTS (SELECT 1 FROM axiom_selection_items si_w "
                    "JOIN axioms a_w ON a_w.hash = si_w.item "
                    "WHERE a_w.id = ae.axiom_id "
                    "AND si_w.selection_name = ?)"
                )
                params.append(name)
            case _:
                msg = f"unknown entity constraint variant: {type(c).__name__}"
                raise ValueError(msg)

    return Predicate(sql=" AND ".join(fragments), params=tuple(params))


def _axiom_predicates(constraints: Sequence[AxiomConstraint]) -> Predicate:
    if not constraints:
        return Predicate(sql="1", params=())

    fragments: list[str] = []
    params: list[object] = []

    for c in constraints:
        match c:
            case WithTypes(tags=tags):
                placeholders = ",".join("?" for _ in tags)
                fragments.append(f"a.type IN ({placeholders})")
                params.extend(tags)
            case MentionsAll(iris=iris):
                for iri in iris:
                    fragments.append(
                        "EXISTS (SELECT 1 FROM axiom_entities ae_m "
                        "WHERE ae_m.axiom_id = a.id "
                        "AND ae_m.entity_iri = ?)"
                    )
                    params.append(iri)
            case MentionsAny(iris=iris):
                placeholders = ",".join("?" for _ in iris)
                fragments.append(
                    "EXISTS (SELECT 1 FROM axiom_entities ae_m "
                    "WHERE ae_m.axiom_id = a.id "
                    f"AND ae_m.entity_iri IN ({placeholders}))"
                )
                params.extend(iris)
            case HasAnyAnnotation(properties=properties):
                placeholders = ",".join("?" for _ in properties)
                fragments.append(
                    "EXISTS (SELECT 1 FROM axiom_text at "
                    f"WHERE at.axiom_id = a.id AND at.property IN ({placeholders}))"
                )
                params.extend(properties)
            case InAxiomSelection(name=name):
                fragments.append(
                    "EXISTS (SELECT 1 FROM axiom_selection_items si_w "
                    "WHERE si_w.item = a.hash "
                    "AND si_w.selection_name = ?)"
                )
                params.append(name)
            case InEntitySelection(name=name):
                fragments.append(
                    "EXISTS (SELECT 1 FROM entity_selection_items si_w "
                    "JOIN axiom_entities ae_w ON ae_w.entity_iri = si_w.item "
                    "WHERE si_w.selection_name = ? "
                    "AND ae_w.axiom_id = a.id)"
                )
                params.append(name)
            case _:
                msg = f"unknown axiom constraint variant: {type(c).__name__}"
                raise ValueError(msg)

    return Predicate(sql=" AND ".join(fragments), params=tuple(params))
