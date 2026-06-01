"""Paginated read of an axiom selection with present/missing accounting."""

from typing import override

from ontoloom.axioms.deserialize import load_axiom
from ontoloom.axioms.hashing import AxiomHash, short_hash
from ontoloom.connection import Session
from ontoloom.errors import StoreCorruptionError
from ontoloom.query.base import Query, RenderedSql, append_pagination
from ontoloom.query.constraints import HasPagination
from ontoloom.selections.store import get_axiom_selection
from ontoloom.selections.types import (
    AxiomItem,
    AxiomSelectionPage,
    SelectionName,
    ShowFilter,
)


def build_show_filter_clause(show: ShowFilter) -> str:
    match show:
        case ShowFilter.ALL:
            return ""
        case ShowFilter.PRESENT:
            return " AND a.id IS NOT NULL"
        case ShowFilter.MISSING:
            return " AND a.id IS NULL"
        case _:
            msg = f"unhandled ShowFilter: {show}"
            raise ValueError(msg)


class ReadAxiomSelection(HasPagination, Query[AxiomSelectionPage]):
    """Paginated read of an axiom selection.

    Page order is insertion order (`id`, which aliases rowid), so any ranking
    baked into the insertion sequence (e.g. exact-match-first in
    `find_axioms`) survives pagination.
    """

    selection: SelectionName
    show: ShowFilter = ShowFilter.ALL

    @override
    def render(self) -> RenderedSql:
        """SQL for the main paginated page query.

        Count queries (total_filtered, present_count) are issued by `_run`; they
        are not part of the rendered statement.
        """
        sql_parts = [
            "SELECT si.item, json(a.data)",
            "FROM axiom_selection_items si LEFT JOIN axioms a ON a.hash = si.item",
            "WHERE si.selection_name = ?",
        ]
        params: list[object] = [self.selection]

        filter_clause = build_show_filter_clause(self.show)
        if filter_clause:
            sql_parts.append(filter_clause.lstrip())

        sql_parts.append("ORDER BY si.id")
        append_pagination(sql_parts, params, self.limit, self.offset)
        return RenderedSql(sql=" ".join(sql_parts), params=tuple(params))

    @override
    def _run(self, s: Session) -> AxiomSelectionPage:
        name = self.selection
        meta = get_axiom_selection(s, name)

        filter_clause = build_show_filter_clause(self.show)

        total_filtered = s.conn.execute(
            "SELECT COUNT(*) FROM axiom_selection_items si "
            "LEFT JOIN axioms a ON a.hash = si.item "
            f"WHERE si.selection_name = ?{filter_clause}",
            (name,),
        ).fetchone()[0]

        present_count = s.conn.execute(
            "SELECT COUNT(*) FROM axiom_selection_items si "
            "JOIN axioms a ON a.hash = si.item "
            "WHERE si.selection_name = ?",
            (name,),
        ).fetchone()[0]

        compiled = self.render()
        rows = s.conn.execute(compiled.sql, compiled.params).fetchall()

        items_list: list[AxiomItem] = []
        for item_hash, data in rows:
            if data is None:
                items_list.append(AxiomItem(hash=AxiomHash(item_hash), axiom=None))
                continue

            try:
                axiom = load_axiom(data)
            except StoreCorruptionError as e:
                msg = f"axiom {short_hash(item_hash)} in ReadAxiomSelection"
                raise StoreCorruptionError(msg, e.original) from e
            items_list.append(AxiomItem(hash=AxiomHash(item_hash), axiom=axiom))
        items = tuple(items_list)

        return AxiomSelectionPage(
            meta=meta,
            items=items,
            total_filtered=total_filtered,
            present=present_count,
            missing=meta.size - present_count,
            show=self.show,
        )
