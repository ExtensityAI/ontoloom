from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology
from ontoloom.history import revert as core_revert

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def revert(
    path: OntologyPath,
    n: int = 1,
):
    """Undo the last N operations (batches) in the current session.

    Events with the same batch_id count as one operation (e.g., `rename_iri`).
    Unbatched events each count as one operation.

    Applies inverses in reverse order. Appends inverse events to the log.
    Skips and reports conflicts (e.g., re-adding a hash that already exists).
    Selections are NOT restored -> they are snapshots; re-search to refresh.
    """
    with Ontology(path) as ont:
        report = core_revert(ont, n)

    parts = [f"Reverted {report.reverted} events across {n} batch(es)."]
    if report.skipped:
        parts.append(f"Skipped {report.skipped} (conflicts).")
    parts.append("")
    parts.extend(report.details)
    return "\n".join(parts)


tool_revert = create_tool(
    revert,
    name="revert",
    annotations=ToolAnnotations(destructiveHint=True),
)
