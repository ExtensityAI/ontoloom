"""Entity search with substring + fuzzy matching."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum

from ontoloom.core.ontology.index.models import EntityEntry
from ontoloom.core.ontology.models.literals import IRI
from rapidfuzz import fuzz

FUZZY_THRESHOLD = 70


class MatchSource(StrEnum):
    IRI = "IRI local name"
    LABEL = "annotation"


class MatchKind(StrEnum):
    EXACT = "substring, exact"
    SUBSTRING = "substring"
    FUZZY = "fuzzy"


_KIND_LIST = list(MatchKind)
_SOURCE_LIST = list(MatchSource)


@dataclass
class SearchResult:
    iri: IRI
    entry: EntityEntry
    source: MatchSource
    kind: MatchKind
    matched_text: str
    score: int = 100

    @property
    def _sort_key(self) -> tuple[int, int, int]:
        return (_KIND_LIST.index(self.kind), _SOURCE_LIST.index(self.source), -self.score)


class Scope(StrEnum):
    IRI = "iri"
    ANNOTATIONS = "annotations"
    ALL = "all"


def _annotation_texts(entry: EntityEntry) -> Iterator[str]:
    for ann in entry.annotations:
        if isinstance(ann.value, str):
            yield ann.value
        else:
            yield ann.value.value


def _check_match(query_lower: str, query_len: int, target: str) -> tuple[MatchKind, int] | None:
    target_lower = target.lower()
    if query_lower == target_lower:
        return MatchKind.EXACT, 100
    if query_lower in target_lower:
        return MatchKind.SUBSTRING, 100
    target_len = len(target_lower)
    if target_len > query_len * 3 or target_len < query_len // 3:
        return None
    score = int(fuzz.ratio(query_lower, target_lower))
    if score >= FUZZY_THRESHOLD:
        return MatchKind.FUZZY, score
    return None


def search_entities(
    entities: dict[IRI, EntityEntry],
    query: str,
    scope: Scope = Scope.ALL,
    max_results: int = 50,
) -> list[SearchResult]:
    """Search entities by name with substring + fuzzy matching."""
    query_lower = query.lower()
    query_len = len(query_lower)
    results: list[SearchResult] = []

    for iri, entry in entities.items():
        candidates: list[SearchResult] = []

        if scope in (Scope.IRI, Scope.ALL):
            for iri_text in (iri.local_name, str(iri)):
                match = _check_match(query_lower, query_len, iri_text)
                if match is not None:
                    kind, score = match
                    candidates.append(
                        SearchResult(iri, entry, MatchSource.IRI, kind, iri_text, score)
                    )

        if scope in (Scope.ANNOTATIONS, Scope.ALL):
            for text in _annotation_texts(entry):
                match = _check_match(query_lower, query_len, text)
                if match is not None:
                    kind, score = match
                    candidates.append(
                        SearchResult(iri, entry, MatchSource.LABEL, kind, text, score)
                    )

        if candidates:
            results.append(min(candidates, key=lambda r: r._sort_key))

    results.sort(key=lambda r: r._sort_key)
    return results[:max_results]
