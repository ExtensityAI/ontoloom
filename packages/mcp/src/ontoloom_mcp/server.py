from fastmcp import FastMCP

from ontoloom_mcp.tools.add_axioms import tool_add_axioms
from ontoloom_mcp.tools.create_ontology import tool_create_ontology
from ontoloom_mcp.tools.describe_ontology import tool_describe_ontology
from ontoloom_mcp.tools.get_axioms import tool_get_axioms
from ontoloom_mcp.tools.get_entity import tool_get_entity
from ontoloom_mcp.tools.remove_axioms import tool_remove_axioms
from ontoloom_mcp.tools.search_axiom_annotations import tool_search_axiom_annotations
from ontoloom_mcp.tools.search_entities import tool_search_entities

mcp = FastMCP("ontoloom")

mcp.add_tool(tool_create_ontology)
mcp.add_tool(tool_add_axioms)
mcp.add_tool(tool_remove_axioms)
mcp.add_tool(tool_describe_ontology)
mcp.add_tool(tool_get_entity)
mcp.add_tool(tool_get_axioms)
mcp.add_tool(tool_search_entities)
mcp.add_tool(tool_search_axiom_annotations)

if __name__ == "__main__":
    mcp.run()
