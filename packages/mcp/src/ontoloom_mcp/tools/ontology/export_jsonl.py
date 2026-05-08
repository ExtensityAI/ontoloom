from pathlib import Path

from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology
from ontoloom.export import export_to_jsonl
from ontoloom.transactions import atomic

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, SelectionName


def export_jsonl(path: OntologyPath, output_path: Path, within: SelectionName | None = None):
    """Export axioms to a JSONL file (one axiom per line, sorted by hash).

    - `within`: Export only axioms in this axiom selection (name only, no hash required --
      export is a read operation). Missing hashes are skipped.

    Use for archival, sharing, or version control snapshots.
    """
    ont = Ontology(path)
    with atomic(ont) as s:
        count = export_to_jsonl(s, output_path, within=within)
        if within:
            return f"Exported {count} axioms from selection {str(within)!r} to `{output_path}`."
        return f"Exported {count} axioms to `{output_path}`."


tool_export_jsonl = create_tool(
    export_jsonl, name="export_jsonl", annotations=ToolAnnotations(idempotentHint=True)
)
