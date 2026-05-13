from typing import Annotated

from annotated_types import MinLen
from mcp.types import ToolAnnotations
from ontoloom.axioms.store import annotate_axiom as core_annotate_axiom
from ontoloom.axioms.store import resolve_hash_prefix
from ontoloom.connection import Ontology, session
from ontoloom.hashing import AxiomHashPrefix
from ontoloom.owl.annotations import Annotation
from ontoloom.utils import dedupe

from ontoloom_mcp.components.errors import MissingRequiredError
from ontoloom_mcp.components.formatting import (
    build_refs_per_axiom,
    format_axiom_listing,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def annotate_axiom(
    path: OntologyPath,
    axiom_hash: AxiomHashPrefix,
    add_annotations: Annotated[list[Annotation], MinLen(1)] | None = None,
    remove_annotations: Annotated[list[Annotation], MinLen(1)] | None = None,
):
    """Add or remove annotations on an existing axiom. The axiom's hash does not change.

    Args:
    - `axiom_hash`: Full hash or unambiguous prefix. Use `match_axioms` to find one.
    - `add_annotations`: Annotations to add (deduplicated against existing).
    - `remove_annotations`: Annotations to remove (no-op if absent).
    """
    if add_annotations is None and remove_annotations is None:
        raise MissingRequiredError(("add_annotations", "remove_annotations"))

    ont = Ontology(path)
    with session(ont) as s:
        result = core_annotate_axiom(
            s,
            resolve_hash_prefix(s, axiom_hash),
            add_annotations=add_annotations,
            remove_annotations=remove_annotations,
        )
        refs_per_axiom = build_refs_per_axiom(s, [result.hashed])
        listing = format_axiom_listing([result.hashed], refs_per_axiom=refs_per_axiom)
        n_added = len(result.added)
        n_removed = len(result.removed)
        already_present = len(dedupe(add_annotations or [])) - n_added
        absent = len(dedupe(remove_annotations or [])) - n_removed
        s.commit()

    summary = f"+{n_added} added, {n_removed} removed"
    skipped: list[str] = []
    if already_present:
        skipped.append(f"{already_present} already present")
    if absent:
        skipped.append(f"{absent} absent")
    if skipped:
        summary += f" ({', '.join(skipped)})"
    return f"{summary}:\n\n{listing}"


tool_annotate_axiom = create_tool(
    annotate_axiom, name="annotate_axiom", annotations=ToolAnnotations(idempotentHint=True)
)
