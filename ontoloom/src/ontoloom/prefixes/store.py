from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import ValidationError

from ontoloom.connection import Metadata, Session
from ontoloom.errors import StoreCorruptionError
from ontoloom.owl.iri import IRI
from ontoloom.prefixes.types import (
    BUILTIN_PREFIXES,
    NamespaceIRI,
    PrefixInUseError,
    PrefixName,
    PrefixNotFoundError,
    UndeclaredPrefixError,
)
from ontoloom.query._constraints import InNamespaces
from ontoloom.query._dispatch import run
from ontoloom.query.count_entities import CountEntities


@dataclass(frozen=True, slots=True)
class SetPrefixResult:
    previous_iri: NamespaceIRI | None
    in_use_count: int


def _get_metadata(s: Session) -> Metadata:
    row = s._conn.execute("SELECT data FROM metadata WHERE id = 1").fetchone()
    try:
        return Metadata.model_validate_json(row[0])
    except ValidationError as e:
        msg = "metadata row is malformed"
        raise StoreCorruptionError(msg, e) from e


def _save_metadata(s: Session, meta: Metadata):
    s._conn.execute("UPDATE metadata SET data = ? WHERE id = 1", (meta.model_dump_json(),))


def list_prefixes(s: Session) -> dict[PrefixName, NamespaceIRI]:
    return {PrefixName(k): NamespaceIRI(v) for k, v in _get_metadata(s).prefixes.items()}


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
    meta = _get_metadata(s)
    previous_raw = meta.prefixes.get(name)
    previous_iri = NamespaceIRI(previous_raw) if previous_raw is not None else None
    in_use_count = 0

    if previous_iri is not None and previous_iri != iri:
        in_use_count = run(s, CountEntities(constraints=(InNamespaces(namespaces=(name,)),)))

    _save_metadata(s, meta.model_copy(update={"prefixes": {**meta.prefixes, name: iri}}))
    return SetPrefixResult(previous_iri=previous_iri, in_use_count=in_use_count)


def remove_prefix(s: Session, name: PrefixName):
    meta = _get_metadata(s)
    if name not in meta.prefixes:
        raise PrefixNotFoundError(name)

    count = run(s, CountEntities(constraints=(InNamespaces(namespaces=(name,)),)))
    if count > 0:
        raise PrefixInUseError(name, count)

    new_prefixes = {k: v for k, v in meta.prefixes.items() if k != name}
    _save_metadata(s, meta.model_copy(update={"prefixes": new_prefixes}))


def prefix_usage_counts(s: Session) -> dict[PrefixName, int]:
    """Count how many distinct entities use each registered prefix namespace."""
    registered = list_prefixes(s)
    db_counts = {
        PrefixName(row[0]): row[1]
        for row in s._conn.execute(
            "SELECT substr(entity_iri, 1, instr(entity_iri, ':') - 1) AS prefix, "
            "COUNT(DISTINCT entity_iri) "
            "FROM axiom_entities WHERE instr(entity_iri, ':') > 0 "
            "GROUP BY prefix"
        )
    }
    return {prefix: db_counts.get(prefix, 0) for prefix in registered}
