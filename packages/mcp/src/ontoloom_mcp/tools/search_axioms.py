import re
from typing import Annotated, Literal

from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.core.ontology.index.builder import build_index
from ontoloom.core.ontology.models.literals import IRI
from pydantic import BaseModel, Field

from ontoloom_mcp.components.formatting import format_axiom_listing, format_search_axioms_page
from ontoloom_mcp.components.hashing import compute_hashes, resolve_or_raise
from ontoloom_mcp.components.ontology_file import OntologyPath, open_ontology
from ontoloom_mcp.tools._helpers import format_not_found


class RegexQuery(BaseModel):
    """Search axioms by regex on rendered text."""

    type: Literal["regex"] = "regex"
    pattern: str = Field(description="Regex pattern matched against rendered axiom text")


class IriQuery(BaseModel):
    """Search axioms mentioning a specific IRI."""

    type: Literal["iri"] = "iri"
    iri: IRI = Field(
        description="IRI in `prefix:local_name` format", examples=[":Dog", "owl:Thing"]
    )


class PrefixQuery(BaseModel):
    """Look up specific axioms by hash prefix."""

    type: Literal["prefix"] = "prefix"
    prefixes: list[str] = Field(
        description="Hash prefixes identifying specific axioms (from `search_axioms` or `inspect_entity`)"
    )


SearchQuery = Annotated[
    RegexQuery | IriQuery | PrefixQuery,
    Field(discriminator="type"),
]


def _search_axioms(
    path: OntologyPath,
    query: SearchQuery,
    axiom_types: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """Search for axioms in an ontology. Supports three query modes:
    - `regex`: pattern matched against rendered axiom text
    - `iri`: all axioms mentioning a specific entity
    - `prefix`: look up specific axioms by hash prefix

    Use `axiom_types` to filter by axiom type (e.g. `["SubClassOf"]`), and `limit`/`offset` to paginate.

    Tip: if you don't know exactly what to look for, or your search returns nothing when you expect results,
    refine progressively. Start broad, then narrow:
    1. By IRI: `query={"type": "iri", "iri": ":Dog"}` — all axioms mentioning `:Dog`
    2. Add `axiom_types=["SubClassOf"]` — only `SubClassOf` axioms for `:Dog`
    3. By regex: `query={"type": "regex", "pattern": "Dog.*Animal"}` — axioms matching a pattern
    """
    with open_ontology(path) as (ontology, _):
        if isinstance(query, PrefixQuery):
            hashed = compute_hashes(ontology.axioms)
            matches = resolve_or_raise(hashed, query.prefixes)
            matched_set = {m.axiom for m in matches}  # pyright: ignore[reportUnhashable] # keep this, else pyright complains. we know axioms are hashable.
            matched_hashed = [ha for ha in hashed if ha.axiom in matched_set]
            return format_axiom_listing(matched_hashed)

        if isinstance(query, IriQuery):
            index = build_index(ontology)
            entry = index.entities.get(query.iri)
            if entry is None:
                return format_not_found(query.iri, index)
            candidates = entry.axioms
        else:
            try:
                pattern = re.compile(query.pattern)
            except re.error as e:
                msg = (
                    f"Invalid regex `pattern`: {e}. "
                    f"Example valid patterns: `Dog.*Animal`, `SubClassOf.*:Person`"
                )
                raise ToolError(msg) from e
            candidates = [a for a in ontology.axioms if pattern.search(str(a))]

        if axiom_types:
            type_set = set(axiom_types)
            candidates = [a for a in candidates if a.type in type_set]

        total = len(candidates)
        all_hashed = compute_hashes(tuple(candidates))
        page_hashed = all_hashed[offset : offset + limit]

        return format_search_axioms_page(page_hashed, total, offset)


tool_search_axioms = Tool.from_function(
    _search_axioms,
    name="search_axioms",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
