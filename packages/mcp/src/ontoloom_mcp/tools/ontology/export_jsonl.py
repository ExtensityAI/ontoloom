from pathlib import Path

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.types import OntologyPath


@handle_tool_errors
def _export_jsonl(path: OntologyPath, output_path: Path, select: str = ""):
    """Export axioms to a JSONL file (one axiom per line, sorted by hash).

    - `select`: Export only axioms in this axiom selection (name only, no hash required —
      export is a read operation). Missing hashes are skipped.

    Use for archival, sharing, or version control snapshots.
    """
    with OntologyStore(path) as store:
        count = store.export_jsonl(output_path, select=select or None)
        if select:
            return f"Exported {count} axioms from selection {select!r} to `{output_path}`."
        return f"Exported {count} axioms to `{output_path}`."


tool_export_jsonl = Tool.from_function(
    _export_jsonl,
    name="export_jsonl",
    annotations=ToolAnnotations(idempotentHint=True),
)
