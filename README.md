<!-- TODO: add logo -->

# ontoloom

MCP tools for building and exploring OWL 2 ontologies with AI agents.

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-green.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

ontoloom is an [MCP](https://modelcontextprotocol.io/) server for working with OWL 2 EL ontologies. Each ontology is a single SQLite file with built-in deduplication and text search.

## Example

An agent building and maintaining a solar system ontology.

``````
create_ontology(path="solar.db")
set_prefix(path="solar.db", name="sol", iri="http://example.org/solar-system#")

add_axioms(path="solar.db", axioms=[...])
Added 6, skipped 0 axioms.

```diff
+ [0616d02d] SubClassOf(sol:Star, sol:CelestialBody)
+ [2657de99] SubClassOf(sol:Planet, sol:CelestialBody)
+ [eb7d1df7] SubClassOf(sol:Moon, sol:CelestialBody)
+ [df252968] SubClassOf(sol:TerrestrialPlanet, sol:Planet)
+ [650a7bfe] SubClassOf(sol:Planet, ObjectSomeValuesFrom(sol:orbits, sol:Star))
+ [caf67282] SubClassOf(sol:Moon, ObjectSomeValuesFrom(sol:orbits, sol:CelestialBody))
```
``````

After a few more rounds of additions, the ontology has grown to 42 entities and 172 axioms. The Moon constraint is too loose — moons should orbit planets, not any celestial body:

``````
remove_axioms(path="solar.db", hash_prefixes=["caf67282"])
Removed 1 axioms.

```diff
- [caf67282] SubClassOf(sol:Moon, ObjectSomeValuesFrom(sol:orbits, sol:CelestialBody))
```

add_axioms(path="solar.db", axioms=[...])
Added 1, skipped 0 axioms.

```diff
+ [58253c7e] SubClassOf(sol:Moon, ObjectSomeValuesFrom(sol:orbits, sol:Planet))
```
``````

To add Saturn's missing moons, the agent first checks the pattern by looking at an existing one:

```
search_axioms(path="solar.db", iri="sol:Europa")
Showing 1-4 of 4 results:

[4a485089] Declaration(NamedIndividual, sol:Europa)
[af28f052] ClassAssertion(sol:Moon, sol:Europa)
[fe77f112] ObjectPropertyAssertion(sol:orbits, sol:Europa, sol:Jupiter)
[05e24b95] ObjectPropertyAssertion(sol:hasSatellite, sol:Jupiter, sol:Europa)
```

Then adds Enceladus and Rhea following the same structure:

``````
add_axioms(path="solar.db", axioms=[...])
Added 10, skipped 0 axioms.

```diff
+ [161051ed] Declaration(NamedIndividual, sol:Enceladus)
+ [ef694717] Declaration(NamedIndividual, sol:Rhea)
+ [76b5e1fd] ClassAssertion(sol:Moon, sol:Enceladus)
+ [216366b2] ClassAssertion(sol:Moon, sol:Rhea)
+ [ae43e129] ObjectPropertyAssertion(sol:orbits, sol:Enceladus, sol:Saturn)
+ [c6891748] ObjectPropertyAssertion(sol:orbits, sol:Rhea, sol:Saturn)
+ [2f8b94a6] ObjectPropertyAssertion(sol:hasSatellite, sol:Saturn, sol:Enceladus)
+ [2effe2e8] ObjectPropertyAssertion(sol:hasSatellite, sol:Saturn, sol:Rhea)
+ [bae0bfe4] AnnotationAssertion(rdfs:label, sol:Enceladus, "Enceladus"^^xsd:string)
+ [be77333e] AnnotationAssertion(rdfs:label, sol:Rhea, "Rhea"^^xsd:string)
```
``````

## What you can do with it

- Build an ontology from scratch by talking to an agent
- Poke around an existing one: search entities and axioms, inspect structure
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
