# ontoloom

MCP tools for building and exploring OWL 2 ontologies with AI agents.

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-green.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

ontoloom is an [MCP](https://modelcontextprotocol.io/) server for working with OWL 2 EL ontologies. Each ontology is a single SQLite file. Axioms are typed and validated at the API boundary; identity is a content hash so duplicates can't slip in. Selections (named, persistent sets of axiom hashes or entity IRIs) are the working memory an agent uses to build up a result, narrow it, combine it with another set, then act on it.

## Example

A coding agent organizing a small recipe collection. Each dish is a class, multi-classified across orthogonal axes (cuisine, course, dietary tag, ingredients) so that set algebra over selections answers real questions like "Italian *and* vegetarian" or "mains *minus* vegetarian".

### 1. Build

``````
create_ontology(path="recipes.ontology.db")
Created ontology at `recipes.ontology.db`.

set_prefix(path="recipes.ontology.db", name="rec", iri="http://example.org/recipes#")
Set prefix `rec:` -> `http://example.org/recipes#`

add_axioms(path="recipes.ontology.db", axioms=[...])      # course/cuisine hierarchy
Added 9 axioms, skipped 0 axioms.

```diff
+ [4c0b0fec3fad] Declaration(Class, rec:Dish)
+ [97c59b751f99] Declaration(ObjectProperty, rec:hasIngredient)
+ [e7a51341d2c4] SubClassOf(rec:ItalianDish, rec:Dish)
+ [2590e3c26227] SubClassOf(rec:ThaiDish, rec:Dish)
+ [ea0fe5701a81] SubClassOf(rec:MexicanDish, rec:Dish)
+ [87b23e6809a0] SubClassOf(rec:JapaneseDish, rec:Dish)
+ [52e75f7efb1a] SubClassOf(rec:Appetizer, rec:Dish)
+ [88791572d5e0] SubClassOf(rec:MainCourse, rec:Dish)
+ [5245da5553ec] SubClassOf(rec:Dessert, rec:Dish)
```
``````

Five dishes get classified along their orthogonal axes, then given a couple of `hasIngredient` restrictions each — the existential restriction is EL's bread and butter:

``````
add_axioms(path="recipes.ontology.db", axioms=[...])      # dish classifications
Added 12 axioms, skipped 0 axioms.

```diff
+ [e0e5c41cf082] SubClassOf(rec:Margherita, rec:ItalianDish)
+ [efabef38097e] SubClassOf(rec:Margherita, rec:MainCourse)
+ [5829446bea21] SubClassOf(rec:Margherita, rec:Vegetarian)
+ [6c04db2439be] SubClassOf(rec:Carbonara, rec:ItalianDish)
+ ... (8 more)
```

add_axioms(path="recipes.ontology.db", axioms=[...])      # ingredients (existential restrictions)
Added 10 axioms, skipped 0 axioms.

```diff
+ [f46e321037bd] SubClassOf(rec:Margherita, ObjectSomeValuesFrom(rec:hasIngredient, rec:Tomato))
+ [105935a22275] SubClassOf(rec:Margherita, ObjectSomeValuesFrom(rec:hasIngredient, rec:Mozzarella))
+ [0b796c64253c] SubClassOf(rec:Carbonara, ObjectSomeValuesFrom(rec:hasIngredient, rec:Pasta))
+ ... (7 more)
```

describe_ontology(path="recipes.ontology.db")
25 entities total
By role:
  24 Class
  1 ObjectProperty

31 axioms total
  29 SubClassOf
  2 Declaration

Top 10 entities by axiom count:
  rec:hasIngredient: 11 axioms
  rec:Dish: 8 axioms
  rec:Guacamole: 5 axioms
  rec:MainCourse: 5 axioms
  rec:Margherita: 5 axioms
  ... (5 more)
``````

### 2. Query

Three structural queries, each saving its hits to a named axiom selection. The third one binds two variables — `?D` and `?ing` — to capture every (dish, ingredient) pair in one shot:

``````
match_axioms(path="recipes.ontology.db",
             pattern={"sub_class": "?D", "super_class": "rec:Vegetarian"},
             into="vegetarian")
Saved 2 axioms to "vegetarian".

[5829446bea21] SubClassOf(rec:Margherita, rec:Vegetarian)
[6ca8c8ab3d15] SubClassOf(rec:Guacamole, rec:Vegetarian)

match_axioms(path="recipes.ontology.db",
             pattern={"sub_class": "?D", "super_class": "rec:ItalianDish"},
             into="italian")
Saved 2 axioms to "italian".
...

match_axioms(path="recipes.ontology.db",
             pattern={"sub_class": "?D",
                      "super_class": {"property": "rec:hasIngredient", "filler": "?ing"}},
             into="dish_ingredients")
Saved 10 axioms to "dish_ingredients".

[0b796c64253c] SubClassOf(rec:Carbonara, ObjectSomeValuesFrom(rec:hasIngredient, rec:Pasta))
[105935a22275] SubClassOf(rec:Margherita, ObjectSomeValuesFrom(rec:hasIngredient, rec:Mozzarella))
[6e50b3c8b677] SubClassOf(rec:Guacamole, ObjectSomeValuesFrom(rec:hasIngredient, rec:Lime))
... (7 more)
``````

### 3. Combine

Selections aren't dead-ends — they're persistent values you compose. `intersect` and `diff` over the dishes each match touched, plus a cross-kind move (`axioms_for(entities_in(...))`) that expands "axioms asserting these dishes are vegetarian" into "every axiom about those dishes":

``````
create_selection(path="recipes.ontology.db", name="italian_veg", expr={
  "intersect": [
    {"entities_in": "italian",     "position": "sub_class"},
    {"entities_in": "vegetarian",  "position": "sub_class"}
  ]
})
Saved 1 entity to "italian_veg".

rec:Margherita (Class)

create_selection(path="recipes.ontology.db", name="meaty_mains", expr={
  "diff": [
    {"entities_in": "mains",      "position": "sub_class"},
    {"entities_in": "vegetarian", "position": "sub_class"}
  ]
})
Saved 3 entities to "meaty_mains".

rec:Carbonara (Class)
rec:PadThai (Class)
rec:Sushi (Class)

create_selection(path="recipes.ontology.db", name="veg_axioms", expr={
  "axioms_for": {"entities_in": "vegetarian", "position": "sub_class"}
})
Saved 10 axioms to "veg_axioms".
...
``````

From 2 vegetarian-asserting axioms, the cross-kind expansion picks up all 10 axioms about both vegetarian dishes — a 5x amplification you don't have to enumerate by hand. `list_selections` shows every selection plus the exact expression that produced it:

```
list_selections(path="recipes.ontology.db")
Selections:
  "vegetarian": 2 axioms - source: match_axioms
  "italian": 2 axioms - source: match_axioms
  "dish_ingredients": 10 axioms - source: match_axioms
  "mains": 4 axioms - source: match_axioms
  "veg_axioms": 10 axioms - source: axioms_for(entities_in(vegetarian, position=sub_class))
  "italian_veg": 1 entity - source: intersect(entities_in(italian, position=sub_class), entities_in(vegetarian, position=sub_class))
  "meaty_mains": 3 entities - source: diff(entities_in(mains, position=sub_class), entities_in(vegetarian, position=sub_class))
```

### 4. Cleanup, safely

Time to drop sushi. `get_entity` saves its asserted axioms to a selection; `remove_axioms` then refuses on first call, returning a preview and a confirm token bound to that selection's current contents. Pass the token to apply:

``````
get_entity(path="recipes.ontology.db", iri="rec:Sushi", into="sushi_axioms")
rec:Sushi (Class)

Axioms (asserted): 4
  4 SubClassOf

Saved 4 axioms to "sushi_axioms".

remove_axioms(path="recipes.ontology.db", target={"name": "sushi_axioms"})
Removing 4 axioms in selection "sushi_axioms".

```diff
- [317a4f8b7796] SubClassOf(rec:Sushi, rec:JapaneseDish)
- [a6d6a6a077a4] SubClassOf(rec:Sushi, rec:MainCourse)
- [b270e1009977] SubClassOf(rec:Sushi, ObjectSomeValuesFrom(rec:hasIngredient, rec:Fish))
- [bdcea4ba6c36] SubClassOf(rec:Sushi, ObjectSomeValuesFrom(rec:hasIngredient, rec:Rice))
```

To proceed, call again with confirm="1f693d37".

remove_axioms(path="recipes.ontology.db", target={"name": "sushi_axioms"}, confirm="1f693d37")
Removed 4 axioms (0 already absent). Selection "sushi_axioms" retained.

```diff
- [317a4f8b7796] SubClassOf(rec:Sushi, rec:JapaneseDish)
- [a6d6a6a077a4] SubClassOf(rec:Sushi, rec:MainCourse)
- [b270e1009977] SubClassOf(rec:Sushi, ObjectSomeValuesFrom(rec:hasIngredient, rec:Fish))
- [bdcea4ba6c36] SubClassOf(rec:Sushi, ObjectSomeValuesFrom(rec:hasIngredient, rec:Rice))
```
``````

If the selection's contents change between the preview and the apply, the token is rejected and a fresh preview is shown. The same shape applies to `rename_iri` on a name collision, and to `set_prefix` when it would change the meaning of in-use entities.

### 5. Ship

``````
export_jsonl(path="recipes.ontology.db", output_path="recipes.jsonl")
Exported 27 axioms to `recipes.jsonl`.
``````

One axiom per line, sorted by hash, ready for archival or sharing.

## What you can do with it

- Build an ontology from scratch by talking to an agent
- Poke around an existing one: search by text or structure, inspect entities
- Hand an agent an existing ontology and ask it to clean up or extend
- Dump everything to JSONL for sharing or archival
- Manage prefix mappings and axiom-level annotations

## Concepts

- **Axioms are content-addressed.** Identity is a SHA-256 over canonical logical content, ignoring annotations. Adding the same axiom twice is a no-op; editing a comment on one doesn't change its hash.
- **Entities are derived from axioms.** Classes, properties, and individuals exist because axioms mention them — there is no separate entity table to keep in sync.
- **Selections are persistent working sets.** Built by query tools (`match_axioms`, `find_axioms`, `find_entities`, `find_duplicate_entities`, `get_entity`) or by `create_selection` over set algebra (`union`/`intersect`/`diff`/`axioms_for`/`entities_in`). They are referenced by bare name and consumed by other tools via `within=<name>` (scope) or `into=<name>` (target).
- **Destructive ops are gated by a confirm-with-preview token.** `remove_axioms` by selection, `rename_iri` on collision, and `set_prefix` on an in-use built-in all return a preview + token on the first call and apply on the second. If the underlying state changed in between, the token is rejected and a fresh preview is shown.
- **OWL 2 EL only.** Axioms are typed Pydantic models validated at the API boundary, so anything reaching SQLite is well-formed and within the EL profile.

## Tools

**Setup**
`create_ontology` · `set_prefix` · `remove_prefix`

**Build**
- `add_axioms` — add validated axioms; duplicates are skipped
- `remove_axioms` — remove by hash or by axiom selection (confirm-with-preview)
- `annotate_axiom` — change axiom-level annotations without touching identity
- `replace_axiom` — atomic delete + add for one axiom
- `rename_iri` — rewrite an IRI across all (or scoped) axioms

**Query**
- `describe_ontology` — entity and axiom counts, top entities, prefix mappings
- `get_entity` — roles, annotations, and asserted axiom counts for one entity
- `find_entities` — text search, optionally filtered by role or namespace
- `find_axioms` — text search on axiom-level annotations
- `find_duplicate_entities` — entities sharing the same value for an annotation property
- `match_axioms` — structural pattern matching with `?vars` and `*` wildcards

**Selections**
- `create_selection` — set algebra (`union` / `intersect` / `diff`) and cross-kind ops (`axioms_for` / `entities_in`)
- `read_selection` — paginated view with present/missing visibility
- `list_selections` — show all named selections with provenance
- `remove_selections` — drop one or more selections

**Export**
`export_jsonl` — dump all axioms (or a selection) to a sorted JSONL file

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

Set `ONTOLOOM_WORKSPACE_ROOT=/path/to/workspace` to confine all `Ontology(...)`, `export_jsonl`, and import paths to that directory tree. Useful when running an agent that may take instructions from untrusted documents — the agent can't open or write SQLite files outside the workspace. Unset (default) means unrestricted single-user behavior.

## How it works

Each ontology lives in a single `.db` file that works the same whether it has a dozen axioms or millions. SQLite is the source of truth — there are no editable files alongside the DB, so an agent can't bypass validation by writing one.

The MCP layer is the only writer. Axioms are typed Pydantic models validated at the boundary, hashed by canonical logical content, and inserted by `add_axioms`. Selections persist in the same DB and carry their provenance, so an agent can build up a working set across many turns without shuttling hashes through its context. Destructive consumes are gated by a confirm-with-preview token that's invalidated if the underlying state changes in between.

## Status

Alpha. The pieces work and are in use, but the API isn't frozen yet. Issues and PRs welcome.

## License

BSD-3-Clause — see [LICENSE](LICENSE).
