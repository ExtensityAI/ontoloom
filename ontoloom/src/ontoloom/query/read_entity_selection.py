"""Paginated read of an entity-kind selection with role/label hydration."""

from pydantic import field_validator, model_validator

from ontoloom.connection import Session
from ontoloom.models import FrozenModel
from ontoloom.owl.axioms import Declaration
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query._predicates import CompiledSql
from ontoloom.query._selection_ref import ResolvedSelection
from ontoloom.selections.types import (
    EntityItem,
    EntitySelectionPage,
    SelectionContentHash,
    SelectionKind,
    SelectionKindError,
    SelectionMeta,
    SelectionName,
    SelectionNotFoundError,
    ShowFilter,
)
from ontoloom.text_index import lookup_entity_labels


class ReadEntitySelection(FrozenModel):
    selection: ResolvedSelection
    show: ShowFilter = ShowFilter.ALL
    limit: int | None = None
    offset: int = 0

    @field_validator("selection", mode="after")
    @classmethod
    def _check_entities_kind(cls, v: ResolvedSelection) -> ResolvedSelection:
        if v.kind != SelectionKind.ENTITIES:
            raise SelectionKindError(
                SelectionName(v.bare_name),
                SelectionKind.ENTITIES,
                v.kind,
                "ReadEntitySelection",
            )
        return v

    @model_validator(mode="after")
    def _validate_pagination(self) -> "ReadEntitySelection":
        if self.offset < 0:
            msg = "offset must be >= 0"
            raise ValueError(msg)

        if self.limit is not None and self.limit < 0:
            msg = "limit must be >= 0 if set"
            raise ValueError(msg)

        if self.offset > 0 and self.limit is None:
            msg = "offset > 0 requires limit to be set"
            raise ValueError(msg)

        return self


_EXISTS_FRAGMENT = "EXISTS (SELECT 1 FROM axiom_entities ae WHERE ae.entity_iri = si.item)"


def render(q: ReadEntitySelection) -> CompiledSql:
    """SQL for the main paginated page query.

    Count queries (total_filtered, present_count) are issued by `_run`; they
    are not part of the rendered statement.
    """
    sql_parts = [
        f"SELECT si.item, {_EXISTS_FRAGMENT} AS is_present",
        "FROM selection_items si",
        "WHERE si.selection_name = ?",
    ]
    params: list[object] = [q.selection.bare_name]

    if q.show == ShowFilter.PRESENT:
        sql_parts.append(f"AND {_EXISTS_FRAGMENT}")
    elif q.show == ShowFilter.MISSING:
        sql_parts.append(f"AND NOT {_EXISTS_FRAGMENT}")

    sql_parts.append("ORDER BY si.rowid")

    if q.limit is not None:
        sql_parts.append("LIMIT ?")
        params.append(q.limit)

        if q.offset > 0:
            sql_parts.append("OFFSET ?")
            params.append(q.offset)

    return CompiledSql(sql=" ".join(sql_parts), params=tuple(params))


def _run(s: Session, q: ReadEntitySelection) -> EntitySelectionPage:
    name = SelectionName(q.selection.bare_name)
    meta_row = s._conn.execute(
        "SELECT kind, hash, size, source FROM selections WHERE name = ?", (name,)
    ).fetchone()

    if meta_row is None:
        raise SelectionNotFoundError(name)

    meta = SelectionMeta(
        name=name,
        kind=SelectionKind(meta_row[0]),
        hash=SelectionContentHash(meta_row[1]),
        size=meta_row[2],
        source=meta_row[3],
    )

    filter_clause = ""
    if q.show == ShowFilter.PRESENT:
        filter_clause = f" AND {_EXISTS_FRAGMENT}"
    elif q.show == ShowFilter.MISSING:
        filter_clause = f" AND NOT {_EXISTS_FRAGMENT}"

    total_filtered = s._conn.execute(
        f"SELECT COUNT(*) FROM selection_items si WHERE si.selection_name = ?{filter_clause}",
        (name,),
    ).fetchone()[0]

    present_count = s._conn.execute(
        "SELECT COUNT(DISTINCT si.item) FROM selection_items si "
        "WHERE si.selection_name = ? "
        f"AND {_EXISTS_FRAGMENT}",
        (name,),
    ).fetchone()[0]

    compiled = render(q)
    rows = s._conn.execute(compiled.sql, compiled.params).fetchall()

    present_iris = [iri for iri, is_present in rows if is_present]
    roles_map: dict[str, EntityType] = {}
    labels_map: dict[str, str] = {}

    if present_iris:
        placeholders = ",".join("?" for _ in present_iris)
        roles_map.update(
            (iri, EntityType(role))
            for iri, role in s._conn.execute(
                f"SELECT DISTINCT ae.entity_iri, ae.role FROM axiom_entities ae "
                f"JOIN axioms a ON a.id = ae.axiom_id "
                f"WHERE a.type = '{Declaration.tag()}' AND ae.entity_iri IN ({placeholders})",
                present_iris,
            )
        )
        labels_map.update(
            {k: v for k, v in lookup_entity_labels(s, present_iris).items() if v is not None}
        )

    items = tuple(
        EntityItem(
            iri=IRI(iri),
            present=bool(is_present),
            role=roles_map.get(iri) if is_present else None,
            label=labels_map.get(iri) if is_present else None,
        )
        for iri, is_present in rows
    )

    return EntitySelectionPage(
        meta=meta,
        items=items,
        total_filtered=total_filtered,
        present=present_count,
        missing=meta.size - present_count,
        show=q.show,
    )
