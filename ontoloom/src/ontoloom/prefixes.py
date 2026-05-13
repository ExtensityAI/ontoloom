import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import override

from pydantic import ValidationError

from ontoloom.connection import Metadata, Session, escape_like
from ontoloom.errors import OntoloomError, StoreCorruptionError
from ontoloom.models import TypedStr
from ontoloom.owl.iri import IRI

_PREFIX_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.-]*$")
_NAMESPACE_IRI_PATTERN = re.compile(r"^\S+:\S+$")


class PrefixName(TypedStr):
    """A namespace prefix label (e.g. `ex`, `rdfs`, `owl`)."""

    description = "Prefix name (e.g. 'ex', 'rdfs', 'owl')"
    pattern = r"^[a-zA-Z_][a-zA-Z0-9_.-]*$"
    examples = ("ex", "rdfs", "owl")

    @override
    @classmethod
    def parse(cls, value: str):
        if not _PREFIX_NAME_PATTERN.match(value):
            msg = (
                "PrefixName must start with a letter or underscore and contain only "
                f"letters, digits, '_', '.', '-', got {value!r}"
            )
            raise ValueError(msg)
        return value


class NamespaceIRI(TypedStr):
    """The IRI a prefix expands to (e.g. `http://example.org/`)."""

    description = (
        "Namespace IRI a prefix expands to (e.g. 'http://example.org/', "
        "'https://w3.org/ns/owl#'). Must contain a scheme separator (':') "
        "and no whitespace. Distinct from entity IRIs in 'prefix:local_name' "
        "shorthand."
    )
    pattern = r"^\S+:\S+$"
    examples = ("http://example.org/", "https://w3.org/ns/owl#")

    @override
    @classmethod
    def parse(cls, value: str):
        if not _NAMESPACE_IRI_PATTERN.match(value):
            msg = f"NamespaceIRI must contain ':' and no whitespace, got {value!r}"
            raise ValueError(msg)
        return value


# Always-accepted prefixes — the OWL/RDF/XSD core that any ontology can reference
# without declaring. The empty prefix (e.g. ":Dog") is also accepted as the
# default namespace.
BUILTIN_PREFIXES: frozenset[PrefixName] = frozenset(
    {PrefixName("rdf"), PrefixName("rdfs"), PrefixName("owl"), PrefixName("xsd")}
)


class PrefixNotFoundError(OntoloomError):
    """IRI prefix mapping does not exist."""

    def __init__(self, name: PrefixName):
        self.name = name
        super().__init__(f"No prefix {str(name)!r}.")


class PrefixInUseError(OntoloomError):
    """Prefix removal refused because entities still reference it."""

    def __init__(self, name: PrefixName, count: int):
        self.name = name
        self.count = count
        super().__init__(f"Prefix {str(name)!r} is still used by {count} entities.")


class UndeclaredPrefixError(OntoloomError):
    """An IRI references a prefix that is neither declared nor built-in."""

    def __init__(self, prefixes: frozenset[PrefixName]):
        self.prefixes = prefixes
        sorted_names = ", ".join(repr(str(p)) for p in sorted(prefixes))
        super().__init__(f"Undeclared prefix(es): {sorted_names}.")


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
        in_use_count = s._conn.execute(
            "SELECT COUNT(DISTINCT entity_iri) FROM axiom_entities "
            "WHERE entity_iri LIKE ? || ':%' ESCAPE '\\'",
            (escape_like(name),),
        ).fetchone()[0]

    _save_metadata(s, meta.model_copy(update={"prefixes": {**meta.prefixes, name: iri}}))
    return SetPrefixResult(previous_iri=previous_iri, in_use_count=in_use_count)


def remove_prefix(s: Session, name: PrefixName):
    meta = _get_metadata(s)
    if name not in meta.prefixes:
        raise PrefixNotFoundError(name)

    count = s._conn.execute(
        "SELECT COUNT(DISTINCT entity_iri) FROM axiom_entities "
        "WHERE entity_iri LIKE ? || ':%' ESCAPE '\\'",
        (escape_like(name),),
    ).fetchone()[0]
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
