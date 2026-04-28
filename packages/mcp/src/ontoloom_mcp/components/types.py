from pathlib import Path
from typing import Annotated

from ontoloom.ontology.types import validate_selection_name
from pydantic import AfterValidator, Field

OntologyPath = Annotated[Path, "Path to an `.ontology.db` file"]

SelectionName = Annotated[str, AfterValidator(validate_selection_name)]

# Same shape constraints as SelectionName; `*` and `?` are interpreted as wildcards
# at the call site, not at the type level.
SelectionPattern = Annotated[str, AfterValidator(validate_selection_name)]

Limit = Annotated[int, Field(ge=1, description="Page size, minimum 1")]

HexPrefix = Annotated[str, Field(pattern=r"^[0-9a-fA-F]+$"), AfterValidator(str.lower)]

PrefixName = Annotated[
    str,
    Field(
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_.-]*$",
        description="Prefix name (e.g. 'ex', 'rdfs', 'owl')",
    ),
]
