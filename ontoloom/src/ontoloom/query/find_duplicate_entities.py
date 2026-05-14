"""Find annotation values shared by more than one entity, optionally scoped to a selection."""

from collections import defaultdict

from pydantic import field_validator

from ontoloom.connection import Session
from ontoloom.entities.types import DuplicateGroup, DuplicateResult
from ontoloom.models import FrozenModel
from ontoloom.owl.iri import IRI
from ontoloom.query._predicates import CompiledSql
from ontoloom.query._selection_ref import ResolvedSelection
from ontoloom.selections.types import (
    SelectionKind,
    SelectionKindError,
    SelectionName,
)


class FindDuplicateEntities(FrozenModel):
    annotation_property: IRI
    within: ResolvedSelection | None = None

    @field_validator("within", mode="after")
    @classmethod
    def _check_entities_kind(cls, v: ResolvedSelection | None) -> ResolvedSelection | None:
        if v is not None and v.kind != SelectionKind.ENTITIES:
            raise SelectionKindError(
                SelectionName(v.bare_name),
                SelectionKind.ENTITIES,
                v.kind,
                "FindDuplicateEntities.within",
            )
        return v


def render(q: FindDuplicateEntities) -> CompiledSql:
    outer_join = ""
    inner_join = ""
    params: list[object] = []

    if q.within is not None:
        outer_join = " JOIN selection_items si ON si.item = et.entity_iri AND si.selection_name = ?"
        inner_join = (
            " JOIN selection_items si2 ON si2.item = et2.entity_iri AND si2.selection_name = ?"
        )

    if q.within is not None:
        params.append(q.within.bare_name)
    params.append(q.annotation_property)
    if q.within is not None:
        params.append(q.within.bare_name)
    params.append(q.annotation_property)

    sql = (
        f"SELECT et.text, et.entity_iri"
        f" FROM entity_text et{outer_join}"
        f" WHERE et.property = ?"
        f"   AND EXISTS ("
        f"     SELECT 1 FROM entity_text et2{inner_join}"
        f"     WHERE et2.property = ? AND et2.text = et.text AND et2.entity_iri != et.entity_iri"
        f"   )"
        f" GROUP BY et.text, et.entity_iri"
        f" ORDER BY et.text, et.entity_iri"
    )
    return CompiledSql(sql=sql, params=tuple(params))


def _run(s: Session, q: FindDuplicateEntities) -> DuplicateResult:
    compiled = render(q)
    rows = s._conn.execute(compiled.sql, compiled.params).fetchall()

    by_text: dict[str, list[str]] = defaultdict(list)
    for text, iri in rows:
        by_text[text].append(iri)

    sorted_pairs = sorted(by_text.items(), key=lambda g: len(g[1]), reverse=True)
    groups = tuple(DuplicateGroup(value=value, iris=tuple(iris)) for value, iris in sorted_pairs)
    affected = tuple(dict.fromkeys(iri for group in groups for iri in group.iris))

    return DuplicateResult(
        groups=groups,
        total_groups=len(groups),
        affected_iris=affected,
    )
