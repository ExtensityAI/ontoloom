from mcp.types import ToolAnnotations
from ontoloom.axioms.store import replace_axiom as core_replace_axiom
from ontoloom.connection import Ontology, session
from ontoloom.hashing import AxiomHashPrefix, short_hash
from ontoloom.owl.axioms import Axiom

from ontoloom_mcp.components.formatting import format_diff
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def replace_axiom(
    path: OntologyPath,
    axiom_hash: AxiomHashPrefix,
    new_axiom: Axiom,
):
    """Replace one axiom with a new one (atomic delete + add, single event).

    Old axiom-level annotations are carried forward; any annotations on `new_axiom`
    are discarded -> use `annotate_axiom` afterwards to modify annotations.

    Args:
    - `axiom_hash`: Full hash or unambiguous prefix of the axiom to replace.
    - `new_axiom`: The replacement axiom. Annotations on it are discarded.

    Edge cases:
    - If new content hashes to the same value as old: no-op.
    - If new hash matches a different existing axiom: old is deleted, add is
      skipped (existing preserved with its annotations), event records mapping.
    """
    ont = Ontology(path)
    with session(ont) as s:
        result = core_replace_axiom(s, axiom_hash, new_axiom)
        s.commit()

    if result.was_noop:
        return f"No-op: new axiom has same hash as old ({short_hash(result.old.hash)})."

    summary = f"Replaced [{short_hash(result.old.hash)}] with [{short_hash(result.new.hash)}]."
    if result.was_merged_into_existing:
        summary += " New hash already existed; merged into existing axiom."
    return format_diff([("-", result.old), ("+", result.new)], summary)


tool_replace_axiom = create_tool(
    replace_axiom,
    name="replace_axiom",
    annotations=ToolAnnotations(destructiveHint=True),
)
