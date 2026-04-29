from ontoloom.ontology import selections
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.patterns import Pattern
from ontoloom.ontology.patterns.search import match_axioms as core_match
from ontoloom.ontology.types import SelectionKind

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath, SelectionName


def match_axioms(
    path: OntologyPath,
    pattern: Pattern,
    into: SelectionName,
    within: SelectionName | None = None,
):
    """Find axioms matching a structural pattern. Saves matches to an axiom selection.

    `pattern`: A pattern object (same structure as axioms, with "?var" for variables
    and "*" for wildcards in IRI positions). String IRIs in expression positions are
    shorthand for NamedClass(iri=X).

    - Axiom-level patterns (e.g., SubClassOfPattern) match whole axioms of that type.
    - Expression-level patterns (e.g., ObjectSomeValuesFromPattern) match any axiom
      containing that expression at any depth.

    Variables (?name) enforce cross-position equality: the same variable in two positions
    means both must match the same value. Use create_selection(entities_in=...) afterwards
    to extract entities from the matched axioms.

    `into`: Name for the axiom selection to save results.
    `within`: Optional selection to restrict search to.
    """
    with Ontology(path) as ont:
        result = core_match(ont, pattern, within=within)
        content_hash, cardinality, old_card = selections.write(
            ont, into, SelectionKind.AXIOMS, result.axiom_hashes, "match_axioms"
        )

    msg = f"{result.total} axioms matched → sel@{content_hash} ({cardinality} items)"
    if old_card is not None:
        msg += f" (was {old_card})"
    return msg


tool_match_axioms = create_tool(match_axioms, name="match_axioms")
