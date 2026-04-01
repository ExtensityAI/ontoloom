from collections import Counter

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.core.ontology.index.builder import build_index
from ontoloom.core.ontology.models.axioms import AnnotationAssertion
from ontoloom.core.ontology.models.literals import IRI

from ontoloom_mcp.components.formatting import format_entity_inspect
from ontoloom_mcp.components.hashing import compute_hashes
from ontoloom_mcp.components.ontology_file import OntologyPath, open_ontology
from ontoloom_mcp.tools._helpers import format_not_found


def _inspect_entity(path: OntologyPath, iris: list[IRI]):
    """Inspect one or more entities. Returns roles, annotations, and a summary of asserted axiom counts by type.

    Does NOT include inherited or inferred information. For example, if `:Dog SubClassOf :Animal` and
    `:Animal SubClassOf ObjectSomeValuesFrom(:hasFeature, :Breathing)`, inspecting `:Dog` will show it has
    1 SubClassOf axiom, but will NOT show the inherited breathing feature.

    Use `search_axioms` with an IRI query to see the full axiom details.
    """
    with open_ontology(path) as (ontology, _):
        index = build_index(ontology)
        blocks = []

        for iri in iris:
            entry = index.entities.get(iri)

            if entry is None:
                blocks.append(format_not_found(iri, index))
                continue

            annotation_hashed = compute_hashes(tuple(entry.annotations))

            axiom_counts: Counter[str] = Counter()
            for a in entry.axioms:
                if not (isinstance(a, AnnotationAssertion) and a.subject == iri):
                    axiom_counts[a.type] += 1

            blocks.append(format_entity_inspect(iri, entry.roles, annotation_hashed, axiom_counts))

        return "\n\n".join(blocks)


tool_inspect_entity = Tool.from_function(
    _inspect_entity,
    name="inspect_entity",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
