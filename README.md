# ontoloom

MCP tools for building and exploring OWL 2 ontologies with AI agents.

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-green.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

ontoloom is an [MCP](https://modelcontextprotocol.io/) server for working with OWL 2 EL ontologies. Each ontology is a single SQLite file. Axioms are typed and validated at the API boundary, and identity is a content hash so duplicates can't slip in.

## Example

A coding agent sketches a tiny solar-system ontology. Create the database, declare a prefix, and add the planet hierarchy:

```python
>>> create_ontology(path="solar.ontology.db")
Created ontology at `solar.ontology.db`.

>>> set_prefix(
...     path="solar.ontology.db",
...     name="sol",
...     iri="http://example.org/solar-system#",
... )
Set prefix `sol:` -> `http://example.org/solar-system#`

>>> add_axioms(path="solar.ontology.db", axioms=[...])
Added 6 axioms, skipped 0 axioms.

[bb5496d24bd1] SubClassOf(sol:Star, sol:CelestialBody)
[f3b454b634a3] SubClassOf(sol:Planet, sol:CelestialBody)
[e4e965a69712] SubClassOf(sol:Moon, sol:CelestialBody)
[3f335b35490c] SubClassOf(sol:TerrestrialPlanet, sol:Planet)
[7bc195f4d6a6] SubClassOf(sol:Planet, ObjectSomeValuesFrom(sol:orbits, sol:Star))
[f3de1afbfd6c] SubClassOf(sol:Moon, ObjectSomeValuesFrom(sol:orbits, sol:Planet))
```

Now query the structure. `match_axioms` does structural pattern matching with `?vars`: the same variable in two positions enforces equality, and every solution comes back as a saved selection.

```python
>>> match_axioms(
...     path="solar.ontology.db",
...     pattern={
...         "sub_class": "?body",
...         "super_class": {"property": "sol:orbits", "filler": "?center"},
...     },
...     into="orbits",
... )
Saved 2 axioms to "orbits".

[7bc195f4d6a6] SubClassOf(sol:Planet, ObjectSomeValuesFrom(sol:orbits, sol:Star))
[f3de1afbfd6c] SubClassOf(sol:Moon, ObjectSomeValuesFrom(sol:orbits, sol:Planet))
```

Selections persist across calls and compose. A second match picks up everything asserted about Planet on the LHS; `create_selection` then intersects the two to find the axiom that's *both* about Planet *and* describes an orbital relationship.

```python
>>> match_axioms(
...     path="solar.ontology.db",
...     pattern={"sub_class": "sol:Planet", "super_class": "?super"},
...     into="planet_facts",
... )
Saved 2 axioms to "planet_facts".

[7bc195f4d6a6] SubClassOf(sol:Planet, ObjectSomeValuesFrom(sol:orbits, sol:Star))
[f3b454b634a3] SubClassOf(sol:Planet, sol:CelestialBody)

>>> create_selection(
...     path="solar.ontology.db",
...     name="planet_orbit",
...     expr={"intersect": ["orbits", "planet_facts"]},
... )
Saved 1 axiom to "planet_orbit".

[7bc195f4d6a6] SubClassOf(sol:Planet, ObjectSomeValuesFrom(sol:orbits, sol:Star))
```

## What you can do with it

- Build an ontology from scratch by talking to an agent
- Poke around an existing one: search by text or structure, inspect entities
- Hand an agent an existing ontology and ask it to clean up or extend
- Dump everything to JSONL for sharing or archival
- Manage prefix mappings and axiom-level annotations

## Tools

**Setup**
`create_ontology` | `set_prefix` | `remove_prefix`

**Build**

- `add_axioms` - add validated axioms; duplicates are skipped
- `remove_axioms` - remove by hash or by axiom selection
- `annotate_axiom` - change axiom-level annotations without touching identity
- `replace_axiom` - atomic delete + add for one axiom
- `rename_iri` - rewrite an IRI across all (or scoped) axioms

**Query**

- `describe_ontology` - entity and axiom counts, top entities, prefix mappings
- `get_entity` - roles, annotations, and asserted axiom counts for one entity
- `find_entities` - text search, optionally filtered by role or namespace
- `find_axioms` - text search on axiom-level annotations
- `find_duplicate_entities` - entities sharing the same value for an annotation property
- `match_axioms` - structural pattern matching with `?vars` and `*` wildcards

**Selections** - named, persistent sets of axiom hashes or entity IRIs

- `create_selection` - build from set algebra over existing selections
- `read_selection` - paginated view with present/missing visibility
- `list_selections` - show all named selections
- `remove_selections` - drop one or more selections

**Export**
`export_jsonl` - dump all axioms to a sorted JSONL file

## Getting started

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone git@github.com:ExtensityAI/ontoloom.git
cd ontoloom
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

### Sandboxing (optional)

Set `ONTOLOOM_WORKSPACE_ROOT=/path/to/workspace` to confine all `Ontology(...)`, `export_jsonl`, and import paths to that directory tree. Useful when running an agent that may take instructions from untrusted documents - the agent can't open or write SQLite files outside the workspace. Unset (default) means unrestricted single-user behavior.

## How it works

Each ontology lives in a single `.db` file that works the same whether it has a dozen axioms or millions. SQLite is the source of truth; the MCP layer is the only writer, so axioms are always validated before they reach disk.

Axioms are typed Pydantic models hashed by canonical logical content, ignoring annotations - you can edit a comment without changing the hash, and exact duplicates are caught automatically.

## Status

Alpha. The pieces work and are in use, but the API isn't frozen yet. Issues and PRs welcome.

## License

BSD-3-Clause - see [LICENSE](LICENSE).
