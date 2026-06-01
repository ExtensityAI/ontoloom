from collections.abc import Iterable
from dataclasses import dataclass

from ontoloom.connection import Session
from ontoloom.owl.iri import IRI
from ontoloom.prefixes.types import (
    BUILTIN_PREFIXES,
    NamespaceIRI,
    PrefixInUseError,
    PrefixName,
    PrefixNotFoundError,
    UndeclaredPrefixError,
)
from ontoloom.query.constraints import InAxiomSelection, InEntitySelection, InNamespaces
from ontoloom.query.count_entities import CountEntities
from ontoloom.query.dispatch import execute


@dataclass(frozen=True, slots=True)
class SetPrefixResult:
    previous_iri: NamespaceIRI | None
    in_use_count: int


def list_prefixes(s: Session) -> dict[PrefixName, NamespaceIRI]:
    return {
        PrefixName(name): NamespaceIRI(iri)
        for name, iri in s.conn.execute("SELECT name, namespace_iri FROM prefixes ORDER BY name")
    }


def check_iri_prefixes(s: Session, iris: Iterable[IRI]):
    """Raise `UndeclaredPrefixError` if any IRI uses a prefix that is neither
    declared in this ontology nor in `BUILTIN_PREFIXES`. The empty prefix
    (used by IRIs of the form `:Dog`) must be declared like any other."""
    declared = frozenset(list_prefixes(s))
    allowed = declared | BUILTIN_PREFIXES
    unknown = {PrefixName(iri.prefix) for iri in iris if iri.prefix not in allowed}
    if unknown:
        raise UndeclaredPrefixError(frozenset(unknown))


def set_prefix(s: Session, name: PrefixName, iri: NamespaceIRI) -> SetPrefixResult:
    """Save a prefix mapping. Reports the previous IRI (if any) and how many entities
    currently use the prefix namespace.

    `in_use_count` is reported even when `previous_iri is None` so callers can
    detect first-time declaration of a built-in prefix that is already in
    implicit use (e.g. declaring `rdfs` after axioms have referenced
    `rdfs:label`). The caller decides whether that warrants confirmation.
    """
    row = s.conn.execute("SELECT namespace_iri FROM prefixes WHERE name = ?", (name,)).fetchone()
    previous_iri = NamespaceIRI(row[0]) if row is not None else None
    in_use_count = 0

    if previous_iri != iri:
        in_use_count = execute(s, CountEntities(constraints=(InNamespaces(namespaces=(name,)),)))

    s.conn.execute(
        "INSERT INTO prefixes (name, namespace_iri) VALUES (?, ?) "
        "ON CONFLICT(name) DO UPDATE SET namespace_iri = excluded.namespace_iri",
        (name, iri),
    )
    return SetPrefixResult(previous_iri=previous_iri, in_use_count=in_use_count)


def remove_prefix(s: Session, name: PrefixName):
    row = s.conn.execute("SELECT 1 FROM prefixes WHERE name = ?", (name,)).fetchone()
    if row is None:
        raise PrefixNotFoundError(name)

    count = execute(s, CountEntities(constraints=(InNamespaces(namespaces=(name,)),)))
    if count > 0:
        raise PrefixInUseError(name, count)

    s.conn.execute("DELETE FROM prefixes WHERE name = ?", (name,))


def count_prefix_usage(
    s: Session,
    *,
    within: InAxiomSelection | InEntitySelection | None = None,
) -> dict[PrefixName, int]:
    """Count how many distinct entities use each registered prefix namespace.

    Scoping:
    - within=None: counts entities mentioned by any axiom.
    - within=InAxiomSelection: counts only entities mentioned by axioms in the
      selection.
    - within=InEntitySelection: counts only entities in the selection.
    """
    registered = list_prefixes(s)

    base = (
        "SELECT substr(ae.entity_iri, 1, instr(ae.entity_iri, ':') - 1) AS prefix, "
        "COUNT(DISTINCT ae.entity_iri) "
        "FROM axiom_entities ae"
    )
    filter_clause = " WHERE instr(ae.entity_iri, ':') > 0 "

    match within:
        case None:
            sql = f"{base}{filter_clause}GROUP BY prefix"
            params: tuple[object, ...] = ()
        case InAxiomSelection(name=ax_name):
            sql = (
                f"{base} "
                "JOIN axioms a ON a.id = ae.axiom_id "
                "JOIN axiom_selection_items asi "
                "  ON asi.item = a.hash AND asi.selection_name = ?"
                f"{filter_clause}GROUP BY prefix"
            )
            params = (ax_name,)
        case InEntitySelection(name=en_name):
            sql = (
                f"{base} "
                "JOIN entity_selection_items esi "
                "  ON esi.item = ae.entity_iri AND esi.selection_name = ?"
                f"{filter_clause}GROUP BY prefix"
            )
            params = (en_name,)
        case _:
            msg = f"unhandled within constraint: {within!r}"
            raise ValueError(msg)

    db_counts = {PrefixName(row[0]): row[1] for row in s.conn.execute(sql, params)}
    return {prefix: db_counts.get(prefix, 0) for prefix in registered}
