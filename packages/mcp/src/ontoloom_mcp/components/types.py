from pathlib import Path
from typing import Annotated

from ontoloom.selections.types import SelectionName as _StrictSelectionName
from pydantic import BeforeValidator, Field

OntologyPath = Annotated[Path, "Path to an `.ontology.db` file"]


def _strip_locked_suffix(value: object):
    if isinstance(value, str) and "@" in value:
        return value.split("@", 1)[0]
    return value


# MCP-input SelectionName: accepts `my_sel` or `my_sel@a3f1b2c4` (the locked
# form returned by other tools) and strips the `@hash` suffix before the core
# strict `SelectionName` validates the bare name.
SelectionName = Annotated[_StrictSelectionName, BeforeValidator(_strip_locked_suffix)]

# Same character set as SelectionName plus '*' and '?' for fnmatch globs
# (interpreted at the call site by `remove_selections_by_pattern`).
SelectionPattern = Annotated[
    str,
    Field(
        pattern=r"^[a-zA-Z*?][a-zA-Z0-9._/:*?-]{0,63}$",
        description="Selection name glob: '*' matches any sequence, '?' matches one character",
    ),
]

Limit = Annotated[int, Field(ge=1, description="Page size, minimum 1")]

Offset = Annotated[int, Field(ge=0, description="Pagination offset, zero-indexed")]
