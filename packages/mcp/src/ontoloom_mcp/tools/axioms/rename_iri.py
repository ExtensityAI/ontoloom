from ontoloom.ontology import axioms
from ontoloom.ontology.connection import Ontology

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def rename_iri(
    path: OntologyPath,
    old_iri: str,
    new_iri: str,
    within: str | None = None,
):
    """Rename an IRI across all (or restricted) axioms.

    Finds every axiom mentioning `old_iri`, replaces it with `new_iri`, and
    saves each as an atomic replace event. All events share one batch_id for
    atomic revert. No-op if old_iri is not in use.

    `within`: optional selection name to restrict which axioms are affected.
    """
    with Ontology(path) as ont:
        result = axioms.rename_iri(ont, old_iri, new_iri, within=within)

    actual = [r for r in result.replaced if not r.was_noop]
    noops = [r for r in result.replaced if r.was_noop]

    if not result.replaced:
        return f"No axioms found mentioning {old_iri}. No-op."

    parts = [f"Renamed {old_iri} → {new_iri}: {len(actual)} axioms replaced."]
    if noops:
        parts.append(f"{len(noops)} unchanged (hash collision).")
    parts.append(f"Batch: {result.batch_id}")
    return " ".join(parts)


tool_rename_iri = create_tool(rename_iri, name="rename_iri")
