from ontoloom.ontology import axioms
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.models.axioms import Axiom

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def replace_axiom(
    path: OntologyPath,
    old_hash: str,
    new_axiom: Axiom,
):
    """Atomic delete+add with event tracking.

    Replaces the axiom identified by `old_hash` (prefix or full) with `new_axiom`.
    - If new content hashes to the same value as old: no-op.
    - If new hash matches a different existing axiom: old is deleted, add is
      skipped (existing preserved with its annotations), event records mapping.
    - Annotations on new_axiom are dropped in the collision case.
    """
    with Ontology(path) as ont:
        result = axioms.replace(ont, old_hash, new_axiom)

    if result.was_noop:
        return f"No-op: new axiom has same hash as old ({result.old_hash[:8]})."

    parts = [f"Replaced [{result.old_hash[:8]}] with [{result.new_hash[:8]}]."]
    if result.old_hash != result.new_hash:
        existing = result.new_hash != result.old_hash
        if existing:
            parts.append("New hash already existed; add was idempotent.")
    return " ".join(parts)


tool_replace_axiom = create_tool(replace_axiom, name="replace_axiom")
