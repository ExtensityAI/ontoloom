import fcntl
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from ontoloom.core.ontology.models.ontology import Ontology

from ontoloom_mcp.models.axioms import Axiom
from ontoloom_mcp.models.converters import convert_axiom

OntologyPath = Annotated[Path, "Path to an `.ontology.json` file"]

# debug enabled by default # TODO: make debug switchable
mcp = FastMCP("ontoloom")


@contextmanager
def open_ontology(path: Path):
    """Load an ontology with an exclusive file lock. Yields (ontology, save) where save() writes back."""
    if not path.exists():
        msg = f"'{path}' does not exist. Create it first with create_ontology."
        raise ToolError(msg)

    f = Path(path).open("r+")  # noqa: SIM115
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        ontology = Ontology.model_validate_json(f.read())

        def save(ont: Ontology):
            f.seek(0)
            f.write(ont.model_dump_json(indent=2) + "\n")
            f.truncate()

        yield ontology, save
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


@mcp.tool(name="create_ontology")
def create_ontology(path: OntologyPath):
    """Create a new empty OWL 2 EL ontology file."""
    if path.exists():
        msg = f"'{path}' already exists. Use a different path or load the existing ontology."
        raise ToolError(msg)

    if not path.parent.exists():
        msg = f"Parent directory '{path.parent}' does not exist. Please create it first."
        raise ToolError(msg)

    ontology = Ontology(axioms=())
    path.write_text(ontology.model_dump_json(indent=2) + "\n")

    return f"Created ontology at `{path}`."


@mcp.tool(name="add_axioms")
def add_axioms(path: OntologyPath, axioms: list[Axiom]):
    """Add axioms to an existing ontology file. Duplicates are skipped."""
    converted = [convert_axiom(a) for a in axioms]
    with open_ontology(path) as (ontology, save):
        added = [a for a in converted if a not in ontology.axioms]
        skipped = len(converted) - len(added)

        if added:
            save(
                Ontology(
                    iri=ontology.iri,
                    axioms=(*ontology.axioms, *added),
                )
            )

        parts = []
        if added:
            parts.append(f"{len(added)} added")
        if skipped:
            parts.append(f"{skipped} skipped (duplicate)")
        return f"{', '.join(parts)}. Total: {len(ontology.axioms) + len(added)} axioms."


@mcp.tool(name="list_axioms")
def list_axioms(path: OntologyPath):
    """List all axioms in an ontology file."""
    with open_ontology(path) as (ontology, _save):
        if not ontology.axioms:
            return "Ontology is empty."
        return [a.model_dump() for a in ontology.axioms]


@mcp.tool(name="remove_axioms")
def remove_axioms(path: OntologyPath, axioms: list[Axiom]):
    """Remove axioms from an ontology file. Axioms not found are skipped."""
    to_remove = {convert_axiom(a) for a in axioms}
    with open_ontology(path) as (ontology, save):
        remaining = tuple(a for a in ontology.axioms if a not in to_remove)
        removed = len(ontology.axioms) - len(remaining)

        if removed:
            save(Ontology(iri=ontology.iri, axioms=remaining))

        skipped = len(to_remove) - removed
        parts = []
        if removed:
            parts.append(f"{removed} removed")
        if skipped:
            parts.append(f"{skipped} skipped (not found)")
        return f"{', '.join(parts)}. Total: {len(remaining)} axioms."


if __name__ == "__main__":
    mcp.run()
