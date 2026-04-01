from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.core.ontology.index.builder import build_index
from ontoloom.core.ontology.models.literals import IRI

from ontoloom_mcp.components import search as search_module
from ontoloom_mcp.components.formatting import (
    format_annotation_compact,
    format_annotation_value,
    format_roles,
)
from ontoloom_mcp.components.ontology_file import OntologyPath, open_ontology
from ontoloom_mcp.components.search import MatchKind, Scope, SearchResult

_KIND_HEADERS = {
    MatchKind.EXACT: "Exact matches",
    MatchKind.SUBSTRING: "Substring matches",
    MatchKind.FUZZY: "Fuzzy matches",
}

_LABEL_IRI = IRI("rdfs:label")
_MAX_RESULTS = 50


def _format_result_line(r: SearchResult) -> str:
    label = None
    extra_annotations = []
    for ann in r.entry.annotations:
        if ann.property == _LABEL_IRI and label is None:
            label = format_annotation_value(ann.value)
        elif ann.property != _LABEL_IRI:
            extra_annotations.append(ann)

    line = f"{r.iri} ({format_roles(r.entry.roles)})"
    if label:
        line += f" — rdfs:label: {label}"
    if r.kind == MatchKind.FUZZY:
        line += f" ({r.score})"

    lines = [line]
    lines.extend(f"  {format_annotation_compact(ann)}" for ann in extra_annotations)

    return "\n".join(lines)


def _format_search_results(results: list[SearchResult], query: str, max_results: int) -> str:
    if not results:
        return f'Search: "{query}" — no results.'

    sections: dict[MatchKind, list[SearchResult]] = {}
    for r in results:
        sections.setdefault(r.kind, []).append(r)

    truncated = len(results) == max_results
    count_str = f"{len(results)}+" if truncated else str(len(results))
    noun = "result" if len(results) == 1 else "results"
    lines = [f'Search: "{query}" — {count_str} {noun}']
    if truncated:
        lines.append("(results truncated, narrow your query for more)")
    lines.append("")

    for kind in (MatchKind.EXACT, MatchKind.SUBSTRING, MatchKind.FUZZY):
        group = sections.get(kind)
        if not group:
            continue

        lines.append(f"## {_KIND_HEADERS[kind]}")
        lines.append("")
        lines.extend(_format_result_line(r) for r in group)
        lines.append("")

    return "\n".join(lines).rstrip()


def _search_entities(
    path: OntologyPath,
    query: str,
    scope: Scope = Scope.ALL,
):
    """Search for entities by name with substring and fuzzy matching.

    Searches across IRI local names and annotation values (labels, comments).
    Results are ranked: exact matches first, then substring matches, then fuzzy matches.
    """
    with open_ontology(path) as (ontology, _):
        index = build_index(ontology)
        results = search_module.search_entities(
            index.entities, query, scope=scope, max_results=_MAX_RESULTS
        )
        return _format_search_results(results, query, max_results=_MAX_RESULTS)


tool_search_entities = Tool.from_function(
    _search_entities,
    name="search_entities",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
