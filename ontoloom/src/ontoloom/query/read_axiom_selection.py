"""Paginated read of an axiom-kind selection with present/missing accounting."""

from typing import override

from ontoloom.connection import Session
from ontoloom.hashing import AxiomHash, short_hash
from ontoloom.load import load_axiom
from ontoloom.query.base import Query
from ontoloom.query.constraints import HasPagination
from ontoloom.query.rendered import RenderedSql
from ontoloom.selections.metadata import get_selection_meta
from ontoloom.selections.types import (
    AxiomItem,
    AxiomSelectionName,
    AxiomSelectionPage,
    ShowFilter,
)


def _show_filter_clause(show: ShowFilter) -> str:
    match show:
        case ShowFilter.ALL:
            return ""
        case ShowFilter.PRESENT:
            return " AND a.id IS NOT NULL"
        case ShowFilter.MISSING:
            return " AND a.id IS NULL"


class ReadAxiomSelection(HasPagination, Query[AxiomSelectionPage]):
    selection: AxiomSelectionName
    show: ShowFilter = ShowFilter.ALL

    @override
    def render(self) -> RenderedSql:
        """SQL for the main paginated page query.

        Count queries (total_filtered, present_count) are issued by `_run`; they
        are not part of the rendered statement.
        """
        sql_parts = [
            "SELECT si.item, json(a.data)",
            "FROM selection_items si LEFT JOIN axioms a ON a.hash = si.item",
            "WHERE si.selection_name = ?",
        ]
        params: list[object] = [self.selection.bare]

        filter_clause = _show_filter_clause(self.show)
        if filter_clause:
            sql_parts.append(filter_clause.lstrip())

        sql_parts.append("ORDER BY si.rowid")

        if self.limit is not None:
            sql_parts.append("LIMIT ?")
            params.append(self.limit)

            if self.offset > 0:
                sql_parts.append("OFFSET ?")
                params.append(self.offset)

        return RenderedSql(sql=" ".join(sql_parts), params=tuple(params))

    @override
    def _run(self, s: Session) -> AxiomSelectionPage:
        name = self.selection.bare
        meta = get_selection_meta(s, name)
        filter_clause = _show_filter_clause(self.show)

        total_filtered = s.conn.execute(
            "SELECT COUNT(*) FROM selection_items si "
            "LEFT JOIN axioms a ON a.hash = si.item "
            f"WHERE si.selection_name = ?{filter_clause}",
            (name,),
        ).fetchone()[0]

        present_count = s.conn.execute(
            "SELECT COUNT(*) FROM selection_items si "
            "JOIN axioms a ON a.hash = si.item "
            "WHERE si.selection_name = ?",
            (name,),
        ).fetchone()[0]

        compiled = self.render()
        rows = s.conn.execute(compiled.sql, compiled.params).fetchall()

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
            show=self.show,
        )
