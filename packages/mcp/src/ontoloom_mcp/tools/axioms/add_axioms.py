from typing import Annotated

from annotated_types import MinLen
from mcp.types import ToolAnnotations
from ontoloom.axioms.mutations import add_axioms as core_add_axioms
from ontoloom.connection import Ontology, session
from ontoloom.owl.axioms import Axiom
from ontoloom.selections.types import SelectionKind

from ontoloom_mcp.components.formatting import format_diff, format_kinded_count
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def add_axioms(
    path: OntologyPath,
    axioms: Annotated[list[Axiom], MinLen(1)],
):
    """Add axioms to an existing ontology. Duplicates are skipped. Returns a diff: `+` = added, `=` = skipped."""
    ont = Ontology(path)
    with session(ont) as s:
        result = core_add_axioms(s, axioms)
        s.commit()

    added_count = format_kinded_count(SelectionKind.AXIOMS, len(result.added))
    skipped_count = format_kinded_count(SelectionKind.AXIOMS, len(result.skipped))
    summary = f"Added {added_count}, skipped {skipped_count}."
    entries = [("+", ha) for ha in result.added] + [("=", ha) for ha in result.skipped]
    return format_diff(entries, summary)


tool_add_axioms = create_tool(
    add_axioms, name="add_axioms", annotations=ToolAnnotations(idempotentHint=True)
)
