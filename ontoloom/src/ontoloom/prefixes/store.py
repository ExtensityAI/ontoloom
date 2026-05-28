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
from ontoloom.query.constraints import InNamespaces
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
    declared in this ontology nor in `BUILTIN_PREFIXES`. Empty prefixes
    (default namespace, e.g. `:Dog`) are accepted."""
    declared = frozenset(list_prefixes(s))
    allowed = declared | BUILTIN_PREFIXES
    unknown = {PrefixName(iri.prefix) for iri in iris if iri.prefix and iri.prefix not in allowed}
    if unknown:
        raise UndeclaredPrefixError(frozenset(unknown))


def set_prefix(s: Session, name: PrefixName, iri: NamespaceIRI) -> SetPrefixResult:
    """Save a prefix mapping. Reports the previous IRI and how many entities used it."""
    row = s.conn.execute("SELECT namespace_iri FROM prefixes WHERE name = ?", (name,)).fetchone()
    previous_iri = NamespaceIRI(row[0]) if row is not None else None
    in_use_count = 0

    if previous_iri is not None and previous_iri != iri:
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


def prefix_usage_counts(s: Session) -> dict[PrefixName, int]:
    """Count how many distinct entities use each registered prefix namespace."""
    registered = list_prefixes(s)
    db_counts = {
        PrefixName(row[0]): row[1]
        for row in s.conn.execute(
            "SELECT substr(entity_iri, 1, instr(entity_iri, ':') - 1) AS prefix, "
            "COUNT(DISTINCT entity_iri) "
            "FROM axiom_entities WHERE instr(entity_iri, ':') > 0 "
            "GROUP BY prefix"
        )
    }
    return {prefix: db_counts.get(prefix, 0) for prefix in registered}
