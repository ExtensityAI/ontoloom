import re
from typing import override

from ontoloom.errors import OntoloomError
from ontoloom.models import TypedStr
from ontoloom.owl.prefix_name import PrefixName
from ontoloom.utils import dquoted

_NAMESPACE_IRI_PATTERN = re.compile(r"^\S+:\S+$")


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
            msg = f"NamespaceIRI must contain ':' and no whitespace, got {dquoted(value)}"
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
        super().__init__(f"No prefix {dquoted(name)}.")


class PrefixInUseError(OntoloomError):
    """Prefix removal refused because entities still reference it."""

    def __init__(self, name: PrefixName, count: int):
        self.name = name
        self.count = count
        super().__init__(f"Prefix {dquoted(name)} is still used by {count} entities.")


class UndeclaredPrefixError(OntoloomError):
    """An IRI references a prefix that is neither declared nor built-in."""

    def __init__(self, prefixes: frozenset[PrefixName]):
        self.prefixes = prefixes
        sorted_names = ", ".join(dquoted(p) for p in sorted(prefixes))
        super().__init__(f"Undeclared prefix(es): {sorted_names}.")
