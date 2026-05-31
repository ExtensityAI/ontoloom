from pathlib import Path

from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.export import export_jsonl as _export_jsonl
from ontoloom.selections.types import SelectionKind, SelectionName
from ontoloom.utils import dquoted

from ontoloom_mcp.components.formatting import format_kinded_count
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def export_jsonl(path: OntologyPath, output_path: Path, within: SelectionName | None = None):
    """Export axioms to a JSONL file (one axiom per line, sorted by hash).

    - `within`: Export only axioms in this axiom selection (e.g.
      `"my_sel"`). Export is a read operation, so no hash is required.
      Missing hashes are skipped.

    Use for archival, sharing, or version control snapshots.
    """
    ont = Ontology(path)
    with session(ont) as s:
        result = _export_jsonl(s, output_path, within=within)
        s.commit()

    count = format_kinded_count(SelectionKind.AXIOMS, result.exported)

    if within is not None:
        skipped_note = f" (skipped {result.skipped} missing items)" if result.skipped > 0 else ""
        return (
            f"Exported {count} from selection {dquoted(within)}{skipped_note} to `{output_path}`."
        )

    return f"Exported {count} to `{output_path}`."


tool_export_jsonl = create_tool(
    export_jsonl, name="export_jsonl", annotations=ToolAnnotations(idempotentHint=True)
)
