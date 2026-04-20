<!-- TODO: add logo -->

# ontoloom

MCP tools for building and exploring OWL 2 ontologies with AI agents.

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

ontoloom gives AI agents a structured toolkit for OWL 2 EL ontologies via the [Model Context Protocol](https://modelcontextprotocol.io/). Every axiom is validated against typed Pydantic models on write — malformed structures never reach your store. Ontologies live in single-file SQLite databases with automatic deduplication, text search, and prefix management.

## Example

``````
>>> create_ontology(path="pizzas.db")
Created ontology at `pizzas.db`.

>>> set_prefix(path="pizzas.db", name="pizza", iri="http://example.org/pizza#")
Set prefix `pizza:` → `http://example.org/pizza#`

>>> add_axioms(path="pizzas.db", axioms=[...])  # 4 axioms as typed JSON
Added 4, skipped 0 axioms.

```diff
+ [a1b2c3d4] Declaration(Class(pizza:Pizza))
+ [e5f6a7b8] Declaration(Class(pizza:Margherita))
+ [c9d0e1f2] SubClassOf(pizza:Margherita, pizza:Pizza)
+ [d3e4f5a6] AnnotationAssertion(rdfs:label, pizza:Margherita, "Margherita")
```

>>> search_entities(path="pizzas.db", query="marg")
Showing 1-1 of 1 entities:

  pizza:Margherita (Class) "Margherita"

>>> describe_ontology(path="pizzas.db")
3 entities total
  2 Class
  1 AnnotationProperty

4 axioms total
  2 Declaration
  1 SubClassOf
  1 AnnotationAssertion

Prefixes:
  pizza: → http://example.org/pizza#
``````

## Use cases

- Build an ontology from scratch through conversation with an AI agent
- Explore and query an existing ontology — search entities, browse axioms, inspect structure
- Have an agent enrich, validate, or refactor an ontology
- Export to JSONL for sharing or archival
- Manage prefix mappings and annotations

## Tools

**Create & manage**
`create_ontology` · `set_prefix` · `remove_prefix`

**Build**
- `add_axioms` — add validated axioms, duplicates skipped
- `remove_axioms` — remove by hash prefix
- `annotate_axiom` — update annotations without changing axiom identity

**Query**
- `describe_ontology` — entity/axiom counts and prefix mappings
- `get_entity` — roles, annotations, axiom counts for a single entity
- `search_entities` — text search with role/namespace filters
- `search_axioms` — filter by entity, axiom type, annotation text

**Export**
`export_jsonl` — export all axioms to a sorted JSONL file

## Getting started

**Prerequisites:** Python 3.12, [uv](https://docs.astral.sh/uv/)

```bash
git clone git@github.com:ExtensityAI/ontology-hydra.git
cd ontology-hydra
```

### Claude Code plugin (recommended)

```
/plugins add /path/to/ontoloom/plugins/claude-plugin
```

### Manual MCP configuration

Add to your `.mcp.json` (update paths to match your clone location):

```json
{
  "mcpServers": {
    "ontoloom": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--project", "packages/mcp", "python", "-m", "ontoloom_mcp.server"]
    }
  }
}
```

### Standalone

```bash
uv run --project packages/mcp python -m ontoloom_mcp.server
```

## How it works

- **SQLite per ontology** — each ontology is a single `.db` file. No server, no infrastructure. Portable, scales from dozens to millions of axioms.
- **Typed validation on write** — axioms are Pydantic models validated at the API boundary. Malformed structures are rejected before they reach the store.
- **Content-addressed hashing** — axiom identity is the SHA-256 of canonical logical content, excluding annotations. Adding a comment never changes an axiom's identity. Duplicates are caught automatically.

## Status

Alpha — functional and useful, but pre-1.0. API may change. Feedback welcome.

## License

See [LICENSE](LICENSE) for details.
