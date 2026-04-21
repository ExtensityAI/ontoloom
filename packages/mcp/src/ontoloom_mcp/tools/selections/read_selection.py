from typing import Literal

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.types import OntologyPath


@handle_tool_errors
def _read_selection(
    path: OntologyPath,
    name: str,
    limit: int = 20,
    offset: int = 0,
    show: Literal["all", "present", "missing"] = "all",
):
    """Paginated view of a selection's contents with missing-item visibility.

    - `show`: "all" (default), "present" (only items still in ontology),
      "missing" (only items that have been removed).

    Always includes summary stats (total, present, missing) regardless of filter.
    For bulk verification, dispatch a subagent to paginate and check rather than
    reading everything into your context.
    """
    with OntologyStore(path) as store:
        result = store.read_selection(name, limit=limit, offset=offset, show=show)

    kind = result["kind"]
    content_hash = result["hash"]
    cardinality = result["cardinality"]
    present = result["present"]
    missing = result["missing"]
    total_filtered = result["total_filtered"]
    items = result["items"]

    header = (
        f"Selection {name!r} ({kind}, sel@{content_hash}): "
        f"{cardinality} total ({present} present, {missing} missing)"
    )

    end = offset + len(items)
    showing = f"Showing {offset + 1}-{end} of {total_filtered} (filter: {show}):"

    lines = [header, showing, ""]

    if kind == "axioms":
        for item in items:
            h = item["hash"][:8]
            if item["missing"]:
                lines.append(f"[{h}] *missing*")
            else:
                lines.append(f"[{h}] {item['axiom']}")
    else:  # entities
        for item in items:
            if item["missing"]:
                lines.append(f"{item['iri']} *missing*")
            else:
                lines.append(f"{item['iri']}")

    return "\n".join(lines)


tool_read_selection = Tool.from_function(
    _read_selection,
    name="read_selection",
    annotations=ToolAnnotations(readOnlyHint=True),
)
