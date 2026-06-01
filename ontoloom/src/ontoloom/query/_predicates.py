"""Predicate dispatchers and SQL fragments — internal to the query DSL.

All emitted fragments reference the bind-aliases `ae` (axiom_entities)
and `a` (axioms). Per-query render functions must use these aliases.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from ontoloom.entities.text import OWL_DEPRECATED_PROPERTY
from ontoloom.owl.axioms import Declaration
from ontoloom.query.constraints import (
    AnnotationTextMatches,
    AxiomConstraint,
    Declared,
    Deprecated,
    EntityConstraint,
    EntityTextMatches,
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
class RankTerm:
    """An ORDER BY expression (relevance ranking) with its bind params."""

    sql: str
    params: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class Predicate:
    """An AND-joined SQL fragment with bind params, plus optional ranking.

    `sql == "1"` is the empty-constraint tautology. `rank` is a list of ORDER BY
    expressions a rank-aware query appends before its stable tiebreak; non-ranking
    constraints leave it empty.
    """

    sql: str
    params: tuple[object, ...]
    rank: tuple[RankTerm, ...] = ()


def build_entity_predicate(constraints: Sequence[EntityConstraint]) -> Predicate:  # noqa: C901
    if not constraints:
        return Predicate(sql="1", params=())

    fragments: list[str] = []
    params: list[object] = []
    rank_terms: list[RankTerm] = []

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
            case EntityTextMatches(query=q, properties=properties):
                ql = q.lower()

                def _annotation_exists(op: str, scope: str) -> str:
                    return (
                        "EXISTS (SELECT 1 FROM entity_text et WHERE et.entity_iri = ae.entity_iri "
                        f"AND et.property {scope} AND {op})"
                    )

                if properties:
                    # User scoped the search to specific annotation properties.
                    # Local-name matching is dropped entirely so `properties=` does
                    # what its docstring promises: restrict the search.
                    ann_scope = "IN (" + ",".join("?" for _ in properties) + ")"
                    ann_contains = _annotation_exists("INSTR(LOWER(et.text), ?) > 0", ann_scope)
                    ann_exact = _annotation_exists("LOWER(et.text) = ?", ann_scope)

                    fragments.append(ann_contains)
                    params.extend(properties)  # ann_contains scope
                    params.append(ql)  # ann_contains

                    rank_sql = f"CASE WHEN {ann_exact} THEN 0 ELSE 1 END"
                    rank_params = (*properties, ql)  # ann_exact
                    rank_terms.append(RankTerm(sql=rank_sql, params=rank_params))
                else:
                    # Unscoped: local-name OR any non-local-name annotation.
                    ann_scope = "!= 'local_name'"

                    def _local_name_exists(op: str) -> str:
                        return (
                            "EXISTS (SELECT 1 FROM entity_text et WHERE et.entity_iri = ae.entity_iri "
                            f"AND et.property = 'local_name' AND {op})"
                        )

                    ln_contains = _local_name_exists("INSTR(LOWER(et.text), ?) > 0")
                    ln_exact = _local_name_exists("LOWER(et.text) = ?")
                    ann_contains = _annotation_exists("INSTR(LOWER(et.text), ?) > 0", ann_scope)
                    ann_exact = _annotation_exists("LOWER(et.text) = ?", ann_scope)

                    fragments.append(f"({ln_contains} OR {ann_contains})")
                    params.append(ql)  # ln_contains
                    params.append(ql)  # ann_contains

                    # rank: ordinal CASE, ordered WHENs (first match wins).
                    rank_sql = (
                        f"CASE WHEN {ln_exact} THEN 0 "
                        f"WHEN {ln_contains} THEN 2 "
                        f"WHEN {ann_exact} THEN 1 ELSE 3 END"
                    )
                    rank_params = (ql, ql, ql)  # ln_exact, ln_contains, ann_exact
                    rank_terms.append(RankTerm(sql=rank_sql, params=rank_params))
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

    return Predicate(sql=" AND ".join(fragments), params=tuple(params), rank=tuple(rank_terms))


def build_axiom_predicate(constraints: Sequence[AxiomConstraint]) -> Predicate:  # noqa: C901
    if not constraints:
        return Predicate(sql="1", params=())

    fragments: list[str] = []
    params: list[object] = []
    rank_terms: list[RankTerm] = []

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
            case AnnotationTextMatches(query=q, properties=properties):
                if properties:
                    prop_ph = ",".join("?" for _ in properties)
                    prop_clause = f"AND at.property IN ({prop_ph}) "
                else:
                    prop_clause = ""

                # filter: substring (contains), case-insensitive
                fragments.append(
                    "EXISTS (SELECT 1 FROM axiom_text at "
                    "WHERE at.axiom_id = a.id "
                    f"{prop_clause}AND INSTR(LOWER(at.text), ?) > 0)"
                )
                params.extend(properties)
                params.append(q.lower())

                # rank: exact (=) before substring
                rank_sql = (
                    "CASE WHEN EXISTS (SELECT 1 FROM axiom_text at "
                    "WHERE at.axiom_id = a.id "
                    f"{prop_clause}AND LOWER(at.text) = ?) THEN 0 ELSE 1 END"
                )
                rank_params = (*properties, q.lower())
                rank_terms.append(RankTerm(sql=rank_sql, params=rank_params))
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

    return Predicate(sql=" AND ".join(fragments), params=tuple(params), rank=tuple(rank_terms))
