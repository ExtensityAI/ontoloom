<!-- TODO: add logo -->

# ontoloom

MCP tools for building and exploring OWL 2 ontologies with AI agents.

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-green.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

ontoloom is an [MCP](https://modelcontextprotocol.io/) server for working with OWL 2 EL ontologies. Each ontology is a single SQLite file with built-in deduplication and text search.

## Example

Create an ontology and a prefix:

```
>>> create_ontology(path="pizzas.db")
Created ontology at `pizzas.db`.

>>> set_prefix(path="pizzas.db", name="pizza", iri="http://example.org/pizza#")
Set prefix `pizza:` → `http://example.org/pizza#`
```

Add axioms. Duplicates are skipped:

``````
>>> add_axioms(path="pizzas.db", axioms=[...])
Added 4, skipped 0 axioms.

```diff
+ [a1b2c3d4] Declaration(Class(pizza:Pizza))
+ [e5f6a7b8] Declaration(Class(pizza:Margherita))
+ [c9d0e1f2] SubClassOf(pizza:Margherita, pizza:Pizza)
+ [d3e4f5a6] AnnotationAssertion(rdfs:label, pizza:Margherita, "Margherita")
```
``````

Search and inspect:

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
```

## What you can do with it

- Build an ontology from scratch by talking to an agent
- Poke around an existing one: search for entities, browse axioms
- Hand an agent an existing ontology and ask it to clean up or extend
- Dump everything to JSONL for sharing or archival
- Manage prefix mappings and annotations

## Tools

**Create & manage**
`create_ontology` · `set_prefix` · `remove_prefix`

**Build**
- `add_axioms` — add validated axioms; duplicates are skipped
- `remove_axioms` — remove by hash prefix
- `annotate_axiom` — update annotations without touching axiom identity

**Query**
- `describe_ontology` — entity and axiom counts, plus prefix mappings
- `get_entity` — roles, annotations, and axiom counts for one entity
- `search_entities` — text search, optionally filtered by role or namespace
- `search_axioms` — filter by entity, axiom type, or annotation text

**Export**
`export_jsonl` — dump all axioms to a sorted JSONL file

## Getting started

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone git@github.com:ExtensityAI/ontology-hydra.git
cd ontology-hydra
```

### Claude Code plugin (recommended)

```
/plugins add /path/to/ontoloom/plugins/claude-plugin
```

### Manual MCP configuration

Drop this into your `.mcp.json`, adjusting the paths for your clone:

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

Each ontology lives in a single `.db` file that works the same whether it has a dozen axioms or millions.

Axioms are typed Pydantic models validated at the API boundary, so by the time anything reaches SQLite it's well-formed. Identity is a SHA-256 over canonical logical content, ignoring annotations — you can edit a comment on an axiom without changing its hash, and duplicates get caught automatically.

## Status

Alpha. The pieces all work and I'm using it, but the API isn't frozen yet. Issues and PRs welcome.

## License

BSD-3-Clause — see [LICENSE](LICENSE).
