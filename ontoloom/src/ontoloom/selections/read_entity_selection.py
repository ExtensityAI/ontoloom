"""Paginated read of an entity selection with role/label hydration."""

from collections import defaultdict
from typing import override

from ontoloom.connection import Session
from ontoloom.entities.reader import lookup_entity_labels
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query.base import Query, RenderedSql, append_pagination
from ontoloom.query.constraints import HasPagination
from ontoloom.selections.store import get_entity_selection
from ontoloom.selections.types import (
    EntityItem,
    EntitySelectionPage,
    SelectionName,
    ShowFilter,
)

_EXISTS_FRAGMENT = "EXISTS (SELECT 1 FROM axiom_entities ae WHERE ae.entity_iri = si.item)"


def build_show_filter_clause(show: ShowFilter) -> str:
    match show:
        case ShowFilter.ALL:
            return ""
        case ShowFilter.PRESENT:
            return f" AND {_EXISTS_FRAGMENT}"
        case ShowFilter.MISSING:
            return f" AND NOT {_EXISTS_FRAGMENT}"
        case _:
            msg = f"unhandled ShowFilter: {show}"
            raise ValueError(msg)


class ReadEntitySelection(HasPagination, Query[EntitySelectionPage]):
    """Paginated read of an entity selection.

    Page order is stable and lexicographic on the item IRI. The
    `(selection_name, item)` autoindex provides the ordering for free, so
    paginated reads avoid a temp-sort over the full selection.
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
            f"SELECT si.item, {_EXISTS_FRAGMENT} AS is_present",
            "FROM entity_selection_items si",
            "WHERE si.selection_name = ?",
        ]
        params: list[object] = [self.selection]

        filter_clause = build_show_filter_clause(self.show)
        if filter_clause:
            sql_parts.append(filter_clause.lstrip())

        sql_parts.append("ORDER BY si.item")
        append_pagination(sql_parts, params, self.limit, self.offset)
        return RenderedSql(sql=" ".join(sql_parts), params=tuple(params))

    @override
    def _run(self, s: Session) -> EntitySelectionPage:
        name = self.selection
        meta = get_entity_selection(s, name)

        filter_clause = build_show_filter_clause(self.show)

        total_filtered = s.conn.execute(
            f"SELECT COUNT(*) FROM entity_selection_items si "
            f"WHERE si.selection_name = ?{filter_clause}",
            (name,),
        ).fetchone()[0]

        present_count = s.conn.execute(
            "SELECT COUNT(DISTINCT si.item) FROM entity_selection_items si "
            "WHERE si.selection_name = ? "
            f"AND {_EXISTS_FRAGMENT}",
            (name,),
        ).fetchone()[0]

        compiled = self.render()
        rows = s.conn.execute(compiled.sql, compiled.params).fetchall()

        present_iris = [iri for iri, is_present in rows if is_present]
        roles_map: defaultdict[str, set[EntityType]] = defaultdict(set)
        labels_map: dict[str, str] = {}

        if present_iris:
            placeholders = ",".join("?" for _ in present_iris)
            for iri, role in s.conn.execute(
                f"SELECT DISTINCT ae.entity_iri, ae.role FROM axiom_entities ae "
                f"WHERE ae.role IS NOT NULL AND ae.entity_iri IN ({placeholders})",
                present_iris,
            ):
                roles_map[iri].add(EntityType(role))

            labels_map.update(
                {k: v for k, v in lookup_entity_labels(s, present_iris).items() if v is not None}
            )

        items = tuple(
            EntityItem(
                iri=IRI(iri),
                present=bool(is_present),
                roles=frozenset(roles_map.get(iri, ())) if is_present else frozenset(),
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
            show=self.show,
        )
