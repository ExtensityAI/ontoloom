from fastmcp import FastMCP

from ontoloom_mcp.middleware import LastResortMiddleware, TimingMiddleware
from ontoloom_mcp.tools.axioms.add_axioms import tool_add_axioms
from ontoloom_mcp.tools.axioms.annotate_axiom import tool_annotate_axiom
from ontoloom_mcp.tools.axioms.match_axioms import tool_match_axioms
from ontoloom_mcp.tools.axioms.remove_axioms import tool_remove_axioms
from ontoloom_mcp.tools.axioms.rename_iri import tool_rename_iri
from ontoloom_mcp.tools.axioms.replace_axiom import tool_replace_axiom
from ontoloom_mcp.tools.entities.find_duplicates import tool_find_duplicates
from ontoloom_mcp.tools.entities.get_entity import tool_get_entity
from ontoloom_mcp.tools.entities.search_entities import tool_search_entities
from ontoloom_mcp.tools.history.revert import tool_revert
from ontoloom_mcp.tools.history.show_changes import tool_show_changes
from ontoloom_mcp.tools.ontology.create_ontology import tool_create_ontology
from ontoloom_mcp.tools.ontology.describe_ontology import tool_describe_ontology
from ontoloom_mcp.tools.ontology.export_jsonl import tool_export_jsonl
from ontoloom_mcp.tools.prefixes.remove_prefix import tool_remove_prefix
from ontoloom_mcp.tools.prefixes.set_prefix import tool_set_prefix
from ontoloom_mcp.tools.selections.create_selection import tool_create_selection
from ontoloom_mcp.tools.selections.list_selections import tool_list_selections
from ontoloom_mcp.tools.selections.read_selection import tool_read_selection
from ontoloom_mcp.tools.selections.remove_selections import tool_remove_selections

mcp = FastMCP(
    "ontoloom",
    mask_error_details=False,  # exception messages reach agent context; set True in untrusted/multi-user deployments
    instructions=(
        "OWL 2 EL ontology editor backed by SQLite. Each .ontology.db file is one ontology.\n\n"
        "Entities (classes, properties, individuals) are not managed directly -> they are "
        "derived from axioms. Add/remove axioms to change the ontology.\n\n"
        "Selections are named sets of axiom hashes or entity IRIs that persist across calls. "
        "Use them to build up working sets incrementally: search, save, narrow, combine, "
        "then act (export, delete, inspect). Outputs include 'name@hash' identifiers; pass "
        "that exact form back as `within=` for write operations to confirm the selection "
        "hasn't drifted (optimistic locking)."
    ),
)

mcp.add_middleware(LastResortMiddleware())
mcp.add_middleware(TimingMiddleware())

mcp.add_tool(tool_create_ontology)
mcp.add_tool(tool_add_axioms)
mcp.add_tool(tool_remove_axioms)
mcp.add_tool(tool_annotate_axiom)
mcp.add_tool(tool_replace_axiom)
mcp.add_tool(tool_rename_iri)
mcp.add_tool(tool_describe_ontology)
mcp.add_tool(tool_find_duplicates)
mcp.add_tool(tool_get_entity)
mcp.add_tool(tool_search_entities)
mcp.add_tool(tool_match_axioms)
mcp.add_tool(tool_set_prefix)
mcp.add_tool(tool_remove_prefix)
mcp.add_tool(tool_export_jsonl)
mcp.add_tool(tool_show_changes)
mcp.add_tool(tool_revert)
mcp.add_tool(tool_create_selection)
mcp.add_tool(tool_read_selection)
mcp.add_tool(tool_list_selections)
mcp.add_tool(tool_remove_selections)

if __name__ == "__main__":
    mcp.run()
