from ontoloom.ontology import selections
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.patterns.models import Pattern
from ontoloom.ontology.patterns.search import match_axioms as core_match
from ontoloom.ontology.patterns.search import project_bindings
from ontoloom.ontology.types import SelectionKind

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, SelectionName


def match_axioms(
    path: OntologyPath,
    pattern: Pattern,
    into: SelectionName,
    within: SelectionName | None = None,
    project: dict[str, str] | None = None,
):
    """Find axioms matching a structural pattern. Saves matches to an axiom selection.

    `pattern`: A pattern object (same structure as axioms, with "?var" for variables
    and "*" for wildcards in IRI positions). String IRIs in expression positions are
    shorthand for NamedClass(iri=X).

    - Axiom-level patterns (e.g., SubClassOfPattern) match whole axioms of that type.
    - Expression-level patterns (e.g., ObjectSomeValuesFromPattern) match any axiom
      containing that expression at any depth.

    `into`: Name for the axiom selection to save results.
    `within`: Optional selection to restrict search to.
    `project`: Optional dict mapping variable names to selection names.
      Creates entity selections from variable bindings (e.g., {"?C": "my_classes"}).
      Only projects values that are valid IRIs (skips complex expressions).
    """
    with Ontology(path) as ont:
        result = core_match(ont, pattern, within=within)

        # Save matched axioms to selection
        content_hash, cardinality, old_card = selections.write(
            ont, into, SelectionKind.AXIOMS, result.axiom_hashes, "match_axioms"
        )

        # Project variables into entity selections
        projected: dict[str, int] = {}
        if project:
            for var_name, sel_name in project.items():
                clean_var = var_name.lstrip("?")
                iris = project_bindings(result.all_bindings, clean_var)
                _, proj_card, _ = selections.write(
                    ont, sel_name, SelectionKind.ENTITIES, iris, f"project({clean_var})"
                )
                projected[sel_name] = proj_card

    parts = [f"{result.total} axioms matched → sel@{content_hash} ({cardinality} items)"]
    if old_card is not None:
        parts[0] += f" (was {old_card})"
    if projected:
        for sel_name, count in projected.items():
            parts.append(f"  projected → {sel_name!r} ({count} entities)")
    return "\n".join(parts)


tool_match_axioms = create_tool(match_axioms, name="match_axioms")
