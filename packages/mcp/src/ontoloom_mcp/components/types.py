from pathlib import Path
from typing import Annotated

OntologyPath = Annotated[Path, "Path to an `.ontology.db` file"]
