from dataclasses import dataclass

from pydantic import ValidationError

from ontoloom.connection import Metadata, Session, escape_like
from ontoloom.errors import OntoloomError, StoreCorruptionError


class PrefixNotFoundError(OntoloomError):
    """IRI prefix mapping does not exist."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"No prefix {name!r}.")


class PrefixInUseError(OntoloomError):
    """Prefix removal refused because entities still reference it."""

    def __init__(self, name: str, count: int):
        self.name = name
        self.count = count
        super().__init__(f"Prefix {name!r} is still used by {count} entities.")


@dataclass(frozen=True, slots=True)
class SetPrefixResult:
    previous_iri: str | None
    in_use_count: int


def _get_metadata(s: Session) -> Metadata:
    row = s.conn.execute("SELECT data FROM metadata WHERE id = 1").fetchone()
    try:
        return Metadata.model_validate_json(row[0])
    except ValidationError as e:
        msg = "metadata row is malformed"
        raise StoreCorruptionError(msg, e) from e


def _save_metadata(s: Session, meta: Metadata):
    s.conn.execute("UPDATE metadata SET data = ? WHERE id = 1", (meta.model_dump_json(),))


def list_prefixes(s: Session) -> dict[str, str]:
    return _get_metadata(s).prefixes


def set_prefix(s: Session, name: str, iri: str) -> SetPrefixResult:
    """Save a prefix mapping. Reports the previous IRI and how many entities used it."""
    meta = _get_metadata(s)
    previous_iri = meta.prefixes.get(name)
    in_use_count = 0

    if previous_iri is not None and previous_iri != iri:
        in_use_count = s.conn.execute(
            "SELECT COUNT(DISTINCT entity_iri) FROM axiom_entities "
            "WHERE entity_iri LIKE ? || ':%' ESCAPE '\\'",
            (escape_like(name),),
        ).fetchone()[0]

    _save_metadata(s, meta.model_copy(update={"prefixes": {**meta.prefixes, name: iri}}))
    return SetPrefixResult(previous_iri=previous_iri, in_use_count=in_use_count)


def remove_prefix(s: Session, name: str):
    meta = _get_metadata(s)
    if name not in meta.prefixes:
        raise PrefixNotFoundError(name)

    count = s.conn.execute(
        "SELECT COUNT(DISTINCT entity_iri) FROM axiom_entities "
        "WHERE entity_iri LIKE ? || ':%' ESCAPE '\\'",
        (escape_like(name),),
    ).fetchone()[0]
    if count > 0:
        raise PrefixInUseError(name, count)

    new_prefixes = {k: v for k, v in meta.prefixes.items() if k != name}
    _save_metadata(s, meta.model_copy(update={"prefixes": new_prefixes}))


def prefix_usage_counts(s: Session) -> dict[str, int]:
    """Count how many distinct entities use each registered prefix namespace."""
    registered = list_prefixes(s)
    db_counts = {
        row[0]: row[1]
        for row in s.conn.execute(
            "SELECT substr(entity_iri, 1, instr(entity_iri, ':') - 1) AS prefix, "
            "COUNT(DISTINCT entity_iri) "
            "FROM axiom_entities WHERE instr(entity_iri, ':') > 0 "
            "GROUP BY prefix"
        )
    }
    return {prefix: db_counts.get(prefix, 0) for prefix in registered}
