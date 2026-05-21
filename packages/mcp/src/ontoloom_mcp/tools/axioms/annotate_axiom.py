from typing import Annotated

from annotated_types import MinLen
from mcp.types import ToolAnnotations
from ontoloom.axioms.hashes import resolve_hash_prefix
from ontoloom.axioms.mutations import annotate_axiom as core_annotate_axiom
from ontoloom.connection import Ontology, session
from ontoloom.hashing import AxiomHashPrefix
from ontoloom.models import FrozenModel, make_tag_resolver, tagged, tagged_union_meta
from ontoloom.owl.annotations import Annotation
from ontoloom.utils import dedupe

from ontoloom_mcp.components.formatting import (
    build_refs_per_axiom,
    format_axiom_listing,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


class AddAnnotation(FrozenModel):
    """Add one annotation to an axiom (idempotent: skipped if already present)."""

    add: Annotation


class RemoveAnnotation(FrozenModel):
    """Remove one annotation from an axiom (no-op if absent)."""

    remove: Annotation


_get_annotation_change_tag = make_tag_resolver(
    (AddAnnotation, RemoveAnnotation), union_name="AnnotationChange"
)

AnnotationChange = Annotated[
    tagged(AddAnnotation) | tagged(RemoveAnnotation),
    *tagged_union_meta(_get_annotation_change_tag),
]


def annotate_axiom(
    path: OntologyPath,
    axiom_hash: AxiomHashPrefix,
    changes: Annotated[tuple[AnnotationChange, ...], MinLen(1)],
):
    """Add or remove annotations on an existing axiom. The axiom's hash does not change.

    Args:
    - `axiom_hash`: Full hash or unambiguous prefix. Use `match_axioms` to find one.
    - `changes`: At least one change. Each change is either `{"add": <annotation>}`
      (idempotent: skipped if already present) or `{"remove": <annotation>}`
      (no-op if absent).
    """
    add_annotations: list[Annotation] = []
    remove_annotations: list[Annotation] = []
    for change in changes:
        match change:
            case AddAnnotation(add=ann):
                add_annotations.append(ann)
            case RemoveAnnotation(remove=ann):
                remove_annotations.append(ann)

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
        already_present = len(dedupe(add_annotations)) - n_added
        absent = len(dedupe(remove_annotations)) - n_removed
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
