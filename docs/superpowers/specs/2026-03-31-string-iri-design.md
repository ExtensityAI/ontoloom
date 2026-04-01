# String IRI Refactor

Replace the structured `IRI(prefix, local_name)` Pydantic model with an `IRI` `str` subclass. This eliminates the entire MCP duplicate model layer (~740 lines) since core models can be used directly by MCP tools.

## Motivation

The current `IRI` is a frozen Pydantic model with `prefix: str` and `local_name: str` fields. This forces the MCP layer to maintain a parallel set of models (`models/expressions.py`, `models/axioms.py`) that accept string IRIs, plus a converter layer (`converters.py`) to translate between the two. The prefix and local_name are never used independently in any logic — every consumer calls `str(iri)` or uses `IRI` as a dict key.

## New `IRI` type

A `str` subclass in `ontoloom/core/ontology/models/literals.py`:

- Validates `prefix:local_name` format on construction
- Hashable, comparable, dict-keyable — it IS a `str`
- `.prefix` and `.local_name` properties available when needed (index extraction, future prefix resolution)
- Pydantic serializes as a plain string in JSON
- `__repr__` returns `IRI(":Dog")` for debuggability

```python
class IRI(str):
    # If prefix/local_name splitting becomes a bottleneck, cache the split result.

    def __new__(cls, value: str):
        if ":" not in value or not value.split(":", 1)[1]:
            raise ValueError(...)
        return super().__new__(cls, value)

    @property
    def prefix(self) -> str:
        return self.split(":", 1)[0]

    @property
    def local_name(self) -> str:
        return self.split(":", 1)[1]
```

Needs a `__get_pydantic_core_schema__` classmethod so Pydantic validates string inputs as `IRI` during model deserialization (e.g., parsing `.ontology.json` files).

## What gets deleted

The entire MCP `models/` directory:

- `models/expressions.py` (~130 lines) — duplicate class expression models with string IRIs
- `models/axioms.py` (~340 lines) — duplicate axiom models with string IRIs
- `models/converters.py` (~220 lines) — StrIRI → IRI conversion functions
- `models/iri.py` (~50 lines) — `StrIRI` and typed IRI variants
- `models/__init__.py`

Total: ~740 lines removed.

## What gets updated

### Core library (minimal changes)

- `models/literals.py` — `IRI` rewritten as `str` subclass. `TypedLiteral`, `LangLiteral`, data range types unchanged.
- `models/expressions.py` — constructor calls change from `IRI(prefix="", local_name="Dog")` to `IRI(":Dog")` in docstring examples. Field types stay `iri: IRI`. `__str__` methods stay — they define the rendering contract used by axiom `__str__` methods.
- `models/axioms.py`, `models/assertions.py` — no changes needed, they reference `IRI` which keeps its name.
- `models/ontology.py` — no changes.
- `operations.py` — no changes.
- `index/` — no changes (dict key works the same, `IRI` is still hashable).

### MCP layer (simplification)

- `tools/add_axioms.py` — import `Axiom` from core directly, drop `MCPAxiom` and `convert_axiom`.
- `tools/search_axioms.py` — drop `convert_iri`, use `IRI(query.iri)` directly. `IriQuery.iri` field type changes from `StrIRI` to `IRI`. Preserve `Field(description=..., examples=...)` metadata for the LLM-facing schema.
- `tools/inspect_entity.py` — drop `convert_iri`, use `IRI(iri_str)` directly. `iris` parameter type changes from `list[StrIRI]` to `list[IRI]`. Preserve Field metadata.
- `tools/search_entities.py` — update `IRI(prefix="rdfs", local_name="label")` to `IRI("rdfs:label")`.
- `tools/_helpers.py` — no changes (uses `iri.local_name` which is preserved as a property).
- `components/` — no changes.
- `server.py` — no changes.

### JSON format (breaking change)

Before:
```json
{"type": "NamedClass", "iri": {"prefix": "", "local_name": "Dog"}}
```

After:
```json
{"type": "NamedClass", "iri": ":Dog"}
```

Sample ontologies need regeneration. No backward compatibility — clean break.

## Design decisions

- **`str` subclass over `Annotated[str, ...]`**: subclass preserves `.prefix`/`.local_name` accessors at runtime. `Annotated` returns a plain `str` with no extra interface.
- **No migration path**: sample ontologies are regenerated. Old format is not supported.
- **Properties split on every access**: the `str.split(":", 1)` is trivial and these properties are rarely called. If it becomes a bottleneck, caching can be added later.
- **Core `IRI` used everywhere**: MCP tools accept and return core types directly. No translation layer.
