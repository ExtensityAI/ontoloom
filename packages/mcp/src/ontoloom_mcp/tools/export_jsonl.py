from pathlib import Path

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.core.ontology.store import OntologyStore

from ontoloom_mcp.components.types import OntologyPath


def _export_jsonl(path: OntologyPath, output_path: Path) -> str:
    """Export all axioms to a JSONL file (one axiom per line, sorted by hash).

    Use for archival, sharing, or version control snapshots.
    """
    with OntologyStore(path) as store:
        count = store.export_jsonl(output_path)
        return f"Exported {count} axioms to `{output_path}`."


tool_export_jsonl = Tool.from_function(
    _export_jsonl,
    name="export_jsonl",
    annotations=ToolAnnotations(idempotentHint=True),
)
