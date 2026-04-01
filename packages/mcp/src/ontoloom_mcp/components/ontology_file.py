"""Ontology file loading with file locking."""

import fcntl
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

from fastmcp.exceptions import ToolError
from ontoloom.core.ontology.models.ontology import Ontology

OntologyPath = Annotated[Path, "Path to an `.ontology.json` file"]


@contextmanager
def open_ontology(path: Path, *, write: bool = False):
    """Load an ontology with a file lock. Yields (ontology, save) where save() writes back.

    Uses a shared lock for reads, exclusive lock for writes.
    """
    if not path.exists():
        msg = f"'{path}' does not exist. Create it first with `create_ontology`."
        raise ToolError(msg)

    f = Path(path).open("r+")  # noqa: SIM115 -- we close it manually in finally block
    try:
        fcntl.flock(f, fcntl.LOCK_EX if write else fcntl.LOCK_SH)
        ontology = Ontology.model_validate_json(f.read())

        def save(ont: Ontology):
            f.seek(0)
            f.write(ont.model_dump_json(indent=2) + "\n")
            f.truncate()

        yield ontology, save
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()
