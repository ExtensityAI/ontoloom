import fcntl
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, cast

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from ontoloom.core.ontology.models.ontology import Ontology
from ontoloom.core.ontology.operations import add_axioms, remove_axioms

from ontoloom_mcp.formatting import (
    ExactMatch,
    format_axiom_listing,
    format_axiom_summary,
    format_diff,
    resolve_axiom_ids,
)
from ontoloom_mcp.models.axioms import Axiom as MCPAxiom
from ontoloom_mcp.models.converters import convert_axiom

OntologyPath = Annotated[Path, "Path to an `.ontology.json` file"]

mcp = FastMCP("ontoloom")


@contextmanager
def open_ontology(path: Path):
    """Load an ontology with an exclusive file lock. Yields (ontology, save) where save() writes back."""
    if not path.exists():
        msg = f"'{path}' does not exist. Create it first with create_ontology."
        raise ToolError(msg)

    f = Path(path).open("r+")  # noqa: SIM115 -- we close it manually in finally block
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
def mcp_create_ontology(path: OntologyPath):
    """Create a new empty OWL 2 EL ontology file. Fails if the file already exists."""
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
def mcp_add_axioms(path: OntologyPath, axioms: list[MCPAxiom]):
    """Add axioms to an existing ontology file. Duplicates are skipped. Returns a diff: '+' = added, '=' = skipped."""
    converted = [convert_axiom(a) for a in axioms]
    with open_ontology(path) as (ontology, save):
        new_ontology, result = add_axioms(ontology, converted)

        if result.added:
            save(new_ontology)

        added_set = set(result.added)
        entries = [("+" if a in added_set else "=", a) for a in converted]
        return format_diff(
            entries,
            f"Added {len(result.added)}, skipped {len(result.skipped)}, total {len(new_ontology.axioms)} axioms.",
        )


@mcp.tool(name="describe_ontology")
def mcp_describe_ontology(path: OntologyPath):
    """Get axiom count statistics for an ontology. Returns total count and breakdown by axiom type."""
    with open_ontology(path) as (ontology, _):
        return format_axiom_summary(ontology.axioms)


@mcp.tool(name="list_axioms")
def mcp_list_axioms(path: OntologyPath):
    """List all axioms in an ontology file. Each axiom is shown with a [hash] prefix usable as a target for remove_axioms."""
    with open_ontology(path) as (ontology, _):
        return format_axiom_listing(ontology.axioms)


@mcp.tool(name="remove_axioms")
def mcp_remove_axioms(path: OntologyPath, prefixes: list[str]):
    """Remove axioms by hash prefix (from list_axioms). Each prefix must uniquely match exactly one axiom. Atomic: if any prefix fails to resolve, nothing is removed."""
    with open_ontology(path) as (ontology, save):
        results = resolve_axiom_ids(ontology.axioms, prefixes)

        errors = [r for r in results if not isinstance(r, ExactMatch)]

        if errors:
            raise ToolError("\n\n".join(str(e) for e in errors))

        matches = cast("list[ExactMatch]", results)
        to_remove = {m.axiom for m in matches}  # pyright: ignore[reportUnhashable] -- axioms are hashable
        new_ontology, result = remove_axioms(ontology, to_remove)

        if result.removed:
            save(new_ontology)

        entries = [("-", a) for a in result.removed]
        return format_diff(
            entries,
            f"Removed {len(result.removed)}, total {len(new_ontology.axioms)} axioms.",
        )


if __name__ == "__main__":
    mcp.run()
