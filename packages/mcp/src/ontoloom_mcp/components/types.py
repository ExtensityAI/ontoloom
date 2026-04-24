from pathlib import Path
from typing import Annotated

from pydantic import AfterValidator, Field

OntologyPath = Annotated[Path, "Path to an `.ontology.db` file"]

_MAX_SELECTION_NAME_LEN = 64


def _check_selection_name(v: str) -> str:
    if not v:
        msg = "Selection name must not be empty."
        raise ValueError(msg)
    if "@" in v:
        msg = "Selection names must not contain '@'."
        raise ValueError(msg)
    if len(v) > _MAX_SELECTION_NAME_LEN:
        msg = f"Selection name too long ({len(v)} chars, max {_MAX_SELECTION_NAME_LEN})."
        raise ValueError(msg)
    return v


SelectionName = Annotated[str, AfterValidator(_check_selection_name)]

Limit = Annotated[int, Field(ge=1, description="Page size, minimum 1")]


def _normalize_hex(v: str) -> str:
    return v.lower()


HexPrefix = Annotated[str, Field(pattern=r"^[0-9a-fA-F]+$"), AfterValidator(_normalize_hex)]
