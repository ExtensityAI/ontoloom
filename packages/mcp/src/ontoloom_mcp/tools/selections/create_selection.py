from mcp.types import ToolAnnotations
from ontoloom.ontology import selections
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.types import SelectionKind

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, SelectionName


def create_selection(
    path: OntologyPath,
    name: SelectionName,
    union: list[SelectionName] | None = None,
    intersection: list[SelectionName] | None = None,
    difference: list[SelectionName] | None = None,
    axioms_for: SelectionName | None = None,
    entities_in: SelectionName | None = None,
):
    """Create a selection from set algebra or kind conversion.

    Exactly one operation must be provided:

    Set algebra (all input selections must be the same kind):
    - `union`: Combine items from these selections.
    - `intersection`: Items present in ALL selections.
    - `difference`: Items in first minus subsequent. Order: [A, B, C] = A - B - C.

    Kind conversion (switch between entity and axiom selections):
    - `axioms_for`: Given an entity selection, find all axioms mentioning those entities.
      Use after entity search to shift focus to axiom-level operations.
    - `entities_in`: Given an axiom selection, extract all entities mentioned in those axioms.
      Use after axiom search to explore or annotate the involved entities.

    Overwrites if name exists. Kind is inferred from the operation.

    Composition patterns:
    - "Everything except": search -> select "all", search -> select "exclude",
      create_selection(difference=["all", "exclude"])
    - "Narrow progressively": search_entities -> select, create_selection(axioms_for=...),
      then search_axioms(within=...) for further filtering
    """
    with Ontology(path) as ont:
        content_hash, cardinality, old_cardinality = selections.create(
            ont,
            name,
            union=union,
            intersection=intersection,
            difference=difference,
            axioms_for=axioms_for,
            entities_in=entities_in,
        )

        if union or intersection or difference:
            inputs = union or intersection or difference
            sel = selections.get_info(ont, inputs[0])  # pyright: ignore[reportIndexIssue]
            kind = sel.kind
        elif axioms_for:
            kind = SelectionKind.AXIOMS
        else:
            kind = SelectionKind.ENTITIES

        parts = [f"Selection {name!r} (sel@{content_hash}): {cardinality} {kind}"]
        if old_cardinality is not None:
            parts.append(f"(overwrote previous: {old_cardinality} items)")
        return " ".join(parts)


tool_create_selection = create_tool(
    create_selection, name="create_selection", annotations=ToolAnnotations(idempotentHint=True)
)
