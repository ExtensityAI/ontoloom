from typing import Annotated

from annotated_types import MinLen
from mcp.types import ToolAnnotations
from ontoloom.axioms.store import add_axioms as core_add_axioms
from ontoloom.connection import Ontology, session
from ontoloom.entity_walker import iter_axiom_entities
from ontoloom.owl.axioms import Axiom
from ontoloom.prefixes import check_iri_prefixes

from ontoloom_mcp.components.formatting import format_diff
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def add_axioms(
    path: OntologyPath,
    axioms: Annotated[list[Axiom], MinLen(1)],
):
    """Add axioms to an existing ontology. Duplicates are skipped. Returns a diff: `+` = added, `=` = skipped."""
    ont = Ontology(path)
    with session(ont) as s:
        check_iri_prefixes(
            s,
            (iri for axiom in axioms for iri, _, _ in iter_axiom_entities(axiom)),
        )
        result = core_add_axioms(s, axioms)
        s.commit()

    summary = f"Added {len(result.added)}, skipped {len(result.skipped)} axioms."
    entries = [("+", ha) for ha in result.added] + [("=", ha) for ha in result.skipped]
    return format_diff(entries, summary)


tool_add_axioms = create_tool(
    add_axioms, name="add_axioms", annotations=ToolAnnotations(idempotentHint=True)
)
