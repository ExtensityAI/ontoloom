# ontoloom

An advanced tool for generating, visualizing, and evaluating domain-specific knowledge graphs and ontologies.

## Overview

ontoloom provides a structured framework for building [OWL 2 EL](https://www.w3.org/TR/owl2-profiles/#OWL_2_EL) ontologies. It is organized as a monorepo with the following packages:

| Package        | Path                     | Description                                          |
| -------------- | ------------------------ | ---------------------------------------------------- |
| `ontoloom`     | `ontoloom/`              | Core ontology models (axioms, expressions, literals) |
| `ontoloom-mcp` | `packages/mcp/`          | MCP server exposing ontology tools                   |
| Claude plugin  | `plugins/claude-plugin/` | Claude Code plugin for ontology engineering          |

## MCP Server

The MCP server (`ontoloom-mcp`) exposes ontology manipulation as tools via the [Model Context Protocol](https://modelcontextprotocol.io/):

**TODO**

### Running the MCP server standalone

```bash
uv run --project packages/mcp python -m ontoloom_mcp.server
```

### Adding the MCP server to your Claude Code instance

Add this to your `.mcp.json`:

```json
{
  "mcpServers": {
    "ontoloom": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--project",
        "packages/mcp",
        "python",
        "-m",
        "ontoloom_mcp.server"
      ]
    }
  }
}
```

## Coding Agent Plugins

### Claude Code

The `plugins/claude-plugin/` directory is a [Claude Code plugin](https://docs.anthropic.com/en/docs/claude-code/plugins) that bundles the MCP server configuration and recommended permissions. To use it, install the plugin in Claude Code:

```
/plugins add /path/to/ontoloom/plugins/claude-plugin
```

This gives Claude Code access to the ontology tools, allowing it to create and manipulate OWL 2 EL ontologies directly during a conversation.

## Development

### Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js >= 25 and [pnpm](https://pnpm.io/) (for the viz frontend)

### Setup

```bash
uv sync
```

## License

See [LICENSE](LICENSE) for details.
