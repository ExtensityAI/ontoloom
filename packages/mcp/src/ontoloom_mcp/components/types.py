from pathlib import Path
from typing import Annotated

from pydantic import Field

OntologyPath = Annotated[Path, "Path to an `.ontology.db` file"]

Limit = Annotated[int, Field(ge=1, description="Page size, minimum 1")]

Offset = Annotated[int, Field(ge=0, description="Pagination offset, zero-indexed")]
