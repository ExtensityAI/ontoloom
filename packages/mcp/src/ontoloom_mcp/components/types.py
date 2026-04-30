from pathlib import Path
from typing import Annotated

from ontoloom.ontology.types import validate_selection_name
from pydantic import AfterValidator, Field

OntologyPath = Annotated[Path, "Path to an `.ontology.db` file"]

# Read-only references to a selection: just a bare name.
# Used by tools that read or scope a selection without mutating it
# (search, match, get_entity, describe_ontology, find_duplicates, etc.).
SelectionName = Annotated[str, AfterValidator(validate_selection_name)]

# Same shape constraints as SelectionName; `*` and `?` are interpreted as wildcards
# at the call site, not at the type level.
SelectionPattern = Annotated[str, AfterValidator(validate_selection_name)]

# A: why is page size called Limit?
Limit = Annotated[int, Field(ge=1, description="Page size, minimum 1")]

# A: weird to have all these types here - not sure if good? also, HexPrefix vs PrefixName a bit ambiguous.

HexPrefix = Annotated[str, Field(pattern=r"^[0-9a-fA-F]+$"), AfterValidator(str.lower)]

PrefixName = Annotated[
    str,
    Field(
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_.-]*$",
        description="Prefix name (e.g. 'ex', 'rdfs', 'owl')",
    ),
]
