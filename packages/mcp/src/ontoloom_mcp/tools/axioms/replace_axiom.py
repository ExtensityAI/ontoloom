from mcp.types import ToolAnnotations
from ontoloom.ontology import axioms
from ontoloom.ontology.canonical import truncate_hash
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.models.axioms import Axiom

from ontoloom_mcp.components.formatting import format_diff
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import HexPrefix, OntologyPath


def replace_axiom(
    path: OntologyPath,
    axiom_hash: HexPrefix,
    new_axiom: Axiom,
):
    """Replace one axiom with a new one (atomic delete + add, single event).

    Old axiom-level annotations are carried forward; any annotations on `new_axiom`
    are discarded — use `annotate_axiom` afterwards to modify annotations.

    Args:
    - `axiom_hash`: Full hash or unambiguous prefix of the axiom to replace.
    - `new_axiom`: The replacement axiom. Annotations on it are discarded.

    Edge cases:
    - If new content hashes to the same value as old: no-op.
    - If new hash matches a different existing axiom: old is deleted, add is
      skipped (existing preserved with its annotations), event records mapping.
    """
    with Ontology(path) as ont:
        result = axioms.replace(ont, axiom_hash, new_axiom)

    if result.was_noop:
        return f"No-op: new axiom has same hash as old ({truncate_hash(result.old_hash)})."

    summary = (
        f"Replaced [{truncate_hash(result.old_hash)}] with [{truncate_hash(result.new_hash)}]."
    )
    if result.was_merged_into_existing:
        summary += " New hash already existed; merged into existing axiom."
    return format_diff([("-", result.old), ("+", result.new)], summary)


tool_replace_axiom = create_tool(
    replace_axiom,
    name="replace_axiom",
    annotations=ToolAnnotations(destructiveHint=True),
)
