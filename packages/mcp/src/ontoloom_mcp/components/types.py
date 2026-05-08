from pathlib import Path
from typing import Annotated

from ontoloom.selections.types import SelectionName
from pydantic import AfterValidator, Field

OntologyPath = Annotated[Path, "Path to an `.ontology.db` file"]

# Same shape constraints as SelectionName; `*` and `?` are interpreted as wildcards
# at the call site, not at the type level. Reuses SelectionName's parse for validation.
SelectionPattern = Annotated[str, AfterValidator(SelectionName.parse)]

# A: why is page size called Limit?
Limit = Annotated[int, Field(ge=1, description="Page size, minimum 1")]

Offset = Annotated[int, Field(ge=0, description="Pagination offset, zero-indexed")]

# A: weird to have all these types here - not sure if good? also, HexPrefix vs PrefixName a bit ambiguous.

HexPrefix = Annotated[str, Field(pattern=r"^[0-9a-fA-F]+$"), AfterValidator(str.lower)]

PrefixName = Annotated[
    str,
    Field(
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_.-]*$",
        description="Prefix name (e.g. 'ex', 'rdfs', 'owl')",
    ),
]

NamespaceIRI = Annotated[
    str,
    Field(
        pattern=r"^\S+:\S+$",
        description=(
            "Namespace IRI a prefix expands to (e.g. 'http://example.org/', "
            "'https://w3.org/ns/owl#'). Must contain a scheme separator (':') "
            "and no whitespace. Distinct from entity IRIs in 'prefix:local_name' "
            "shorthand."
        ),
    ),
]

SessionId = Annotated[
    str,
    Field(
        pattern=r"^[0-9a-f]{32}$",
        description="32-character hex session id (UUID4 hex, lowercase).",
    ),
]
