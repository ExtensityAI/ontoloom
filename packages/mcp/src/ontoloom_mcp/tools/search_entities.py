from typing import Literal

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from ontoloom.core.ontology.models.literals import IRI
from ontoloom.core.ontology.store import EntityMatch, OntologyStore

from ontoloom_mcp.components.formatting import format_roles
from ontoloom_mcp.components.types import OntologyPath

_LABEL_IRI = IRI("rdfs:label")
_MAX_RESULTS = 50

_KIND_HEADERS = {
    "exact": "Exact matches",
    "substring": "Substring matches",
}


def _format_result_line(m: EntityMatch) -> str:
    label = None
    extra_annotations = []
    for ann in m.annotations:
        if ann.property == _LABEL_IRI and label is None:
            label = f'"{ann.value}"'
        elif ann.property != _LABEL_IRI:
            extra_annotations.append(ann)

    line = f"{m.iri} ({format_roles(m.roles)})"
    if label:
        line += f" — rdfs:label: {label}"

    lines = [line]
    lines.extend(f'  {ann.property}: "{ann.value}"' for ann in extra_annotations)
    return "\n".join(lines)


def _format_search_results(results: list[EntityMatch], query: str) -> str:
    if not results:
        return f'Search: "{query}" — no results.'

    sections: dict[str, list[EntityMatch]] = {}
    for m in results:
        sections.setdefault(m.match_quality, []).append(m)

    truncated = len(results) == _MAX_RESULTS
    count_str = f"{len(results)}+" if truncated else str(len(results))
    noun = "result" if len(results) == 1 else "results"
    lines = [f'Search: "{query}" — {count_str} {noun}']
    if truncated:
        lines.append("(results truncated, narrow your query for more)")
    lines.append("")

    for quality in ("exact", "substring"):
        group = sections.get(quality)
        if not group:
            continue
        lines.append(f"## {_KIND_HEADERS[quality]}")
        lines.append("")
        lines.extend(_format_result_line(m) for m in group)
        lines.append("")

    return "\n".join(lines).rstrip()


def _search_entities(
    path: OntologyPath,
    query: str,
    scope: Literal["iri", "annotations", "all"] = "all",
):
    """Search for entities by name with substring matching.

    Searches across IRI local names and annotation values (labels, comments).
    Results are ranked: exact matches first, then substring matches.
    """
    with OntologyStore(path) as store:
        results = store.search_entities(query, scope=scope, limit=_MAX_RESULTS)
        return _format_search_results(results, query)


tool_search_entities = Tool.from_function(
    _search_entities,
    name="search_entities",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
)
