"""Paginated read of an axiom-kind selection with present/missing accounting."""

from pydantic import field_validator, model_validator

from ontoloom.connection import Session
from ontoloom.hashing import AxiomHash, short_hash
from ontoloom.load import load_axiom
from ontoloom.models import FrozenModel
from ontoloom.query._predicates import CompiledSql
from ontoloom.query._selection_ref import ResolvedSelection
from ontoloom.selections.types import (
    AxiomItem,
    AxiomSelectionPage,
    SelectionContentHash,
    SelectionKind,
    SelectionKindError,
    SelectionMeta,
    SelectionName,
    SelectionNotFoundError,
    ShowFilter,
)


class ReadAxiomSelection(FrozenModel):
    selection: ResolvedSelection
    show: ShowFilter = ShowFilter.ALL
    limit: int | None = None
    offset: int = 0

    @field_validator("selection", mode="after")
    @classmethod
    def _check_axioms_kind(cls, v: ResolvedSelection) -> ResolvedSelection:
        if v.kind != SelectionKind.AXIOMS:
            raise SelectionKindError(
                SelectionName(v.bare_name),
                SelectionKind.AXIOMS,
                v.kind,
                "ReadAxiomSelection",
            )
        return v

    @model_validator(mode="after")
    def _validate_pagination(self) -> "ReadAxiomSelection":
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


def render(q: ReadAxiomSelection) -> CompiledSql:
    """SQL for the main paginated page query.

    Count queries (total_filtered, present_count) are issued by `_run`; they
    are not part of the rendered statement.
    """
    sql_parts = [
        "SELECT si.item, json(a.data)",
        "FROM selection_items si LEFT JOIN axioms a ON a.hash = si.item",
        "WHERE si.selection_name = ?",
    ]
    params: list[object] = [q.selection.bare_name]

    if q.show == ShowFilter.PRESENT:
        sql_parts.append("AND a.id IS NOT NULL")
    elif q.show == ShowFilter.MISSING:
        sql_parts.append("AND a.id IS NULL")

    sql_parts.append("ORDER BY si.rowid")

    if q.limit is not None:
        sql_parts.append("LIMIT ?")
        params.append(q.limit)

        if q.offset > 0:
            sql_parts.append("OFFSET ?")
            params.append(q.offset)

    return CompiledSql(sql=" ".join(sql_parts), params=tuple(params))


def _run(s: Session, q: ReadAxiomSelection) -> AxiomSelectionPage:
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
        filter_clause = " AND a.id IS NOT NULL"
    elif q.show == ShowFilter.MISSING:
        filter_clause = " AND a.id IS NULL"

    total_filtered = s._conn.execute(
        "SELECT COUNT(*) FROM selection_items si "
        "LEFT JOIN axioms a ON a.hash = si.item "
        f"WHERE si.selection_name = ?{filter_clause}",
        (name,),
    ).fetchone()[0]

    present_count = s._conn.execute(
        "SELECT COUNT(*) FROM selection_items si "
        "JOIN axioms a ON a.hash = si.item "
        "WHERE si.selection_name = ?",
        (name,),
    ).fetchone()[0]

    compiled = render(q)
    rows = s._conn.execute(compiled.sql, compiled.params).fetchall()

    items = tuple(
        AxiomItem(
            hash=AxiomHash(item_hash),
            axiom=(
                load_axiom(data, f"axiom {short_hash(item_hash)} in ReadAxiomSelection")
                if data is not None
                else None
            ),
        )
        for item_hash, data in rows
    )

    return AxiomSelectionPage(
        meta=meta,
        items=items,
        total_filtered=total_filtered,
        present=present_count,
        missing=meta.size - present_count,
        show=q.show,
    )
