from fastmcp.tools import Tool
from ontoloom.ontology.store import OntologyStore

from ontoloom_mcp.components.errors import handle_tool_errors
from ontoloom_mcp.components.types import OntologyPath


@handle_tool_errors
def _create_selection(
    path: OntologyPath,
    name: str,
    union: list[str] = [],  # noqa: B006
    intersection: list[str] = [],  # noqa: B006
    difference: list[str] = [],  # noqa: B006
    axioms_for: str = "",
    entities_in: str = "",
):
    """Create a selection from set algebra or type conversion.

    Exactly one operation must be provided:
    - `union`: Combine items from these selections (all must be same kind).
    - `intersection`: Items present in ALL selections (all must be same kind).
    - `difference`: Items in first minus subsequent. Order: [A, B, C] = A - B - C.
    - `axioms_for`: Given an entity selection, create an axiom selection of all axioms
      mentioning those entities.
    - `entities_in`: Given an axiom selection, create an entity selection of all entities
      mentioned in those axioms.

    Overwrites if name exists. Kind is inferred from the operation.

    Composition patterns:
    - "Everything except": search → select "all", search → select "keep",
      create_selection(difference=["all", "keep"])
    - "Narrow progressively": search_entities → select, create_selection(axioms_for=...),
      then search_axioms(within=...) for further filtering
    """
    if "@" in name:
        msg = "Selection names must not contain '@'."
        raise ValueError(msg)

    with OntologyStore(path) as store:
        content_hash, cardinality, old_cardinality = store.create_selection(
            name,
            union=union or None,
            intersection=intersection or None,
            difference=difference or None,
            axioms_for=axioms_for or None,
            entities_in=entities_in or None,
        )

        # Determine kind from the operation
        if union or intersection or difference:
            inputs = union or intersection or difference
            sel = store._get_selection(inputs[0])
            kind = sel["kind"]
        elif axioms_for:
            kind = "axioms"
        else:
            kind = "entities"

        parts = [f"Selection {name!r} (sel@{content_hash}): {cardinality} {kind}"]
        if old_cardinality is not None:
            parts.append(f"(overwrote previous: {old_cardinality} items)")
        return " ".join(parts)


tool_create_selection = Tool.from_function(
    _create_selection,
    name="create_selection",
)
