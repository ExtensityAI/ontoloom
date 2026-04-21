from fastmcp import FastMCP

from ontoloom_mcp.tools.axioms.add_axioms import tool_add_axioms
from ontoloom_mcp.tools.axioms.annotate_axiom import tool_annotate_axiom
from ontoloom_mcp.tools.axioms.remove_axioms import tool_remove_axioms
from ontoloom_mcp.tools.axioms.search_axioms import tool_search_axioms
from ontoloom_mcp.tools.entities.get_entity import tool_get_entity
from ontoloom_mcp.tools.entities.search_entities import tool_search_entities
from ontoloom_mcp.tools.ontology.create_ontology import tool_create_ontology
from ontoloom_mcp.tools.ontology.describe_ontology import tool_describe_ontology
from ontoloom_mcp.tools.ontology.export_jsonl import tool_export_jsonl
from ontoloom_mcp.tools.prefixes.remove_prefix import tool_remove_prefix
from ontoloom_mcp.tools.prefixes.set_prefix import tool_set_prefix
from ontoloom_mcp.tools.selections.create_selection import tool_create_selection
from ontoloom_mcp.tools.selections.drop_selection import tool_drop_selection
from ontoloom_mcp.tools.selections.list_selections import tool_list_selections
from ontoloom_mcp.tools.selections.read_selection import tool_read_selection

mcp = FastMCP("ontoloom")

mcp.add_tool(tool_create_ontology)
mcp.add_tool(tool_add_axioms)
mcp.add_tool(tool_remove_axioms)
mcp.add_tool(tool_annotate_axiom)
mcp.add_tool(tool_describe_ontology)
mcp.add_tool(tool_get_entity)
mcp.add_tool(tool_search_entities)
mcp.add_tool(tool_search_axioms)
mcp.add_tool(tool_set_prefix)
mcp.add_tool(tool_remove_prefix)
mcp.add_tool(tool_export_jsonl)
mcp.add_tool(tool_create_selection)
mcp.add_tool(tool_read_selection)
mcp.add_tool(tool_list_selections)
mcp.add_tool(tool_drop_selection)

if __name__ == "__main__":
    mcp.run()
