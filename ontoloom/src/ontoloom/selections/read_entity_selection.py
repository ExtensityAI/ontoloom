"""Paginated read of an entity-kind selection with role/label hydration."""

from typing import override

from ontoloom.connection import Session
from ontoloom.entities.reader import lookup_entity_labels
from ontoloom.owl.axioms import Declaration
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.query.base import Query, RenderedSql, append_pagination
from ontoloom.query.constraints import HasPagination
from ontoloom.selections.store import get_selection
from ontoloom.selections.types import (
    EntityItem,
    EntitySelectionName,
    EntitySelectionPage,
    SelectionKind,
    SelectionKindMismatchError,
    ShowFilter,
)

_EXISTS_FRAGMENT = "EXISTS (SELECT 1 FROM axiom_entities ae WHERE ae.entity_iri = si.item)"


def _show_filter_clause(show: ShowFilter) -> str:
    match show:
        case ShowFilter.ALL:
            return ""
        case ShowFilter.PRESENT:
            return f" AND {_EXISTS_FRAGMENT}"
        case ShowFilter.MISSING:
            return f" AND NOT {_EXISTS_FRAGMENT}"


class ReadEntitySelection(HasPagination, Query[EntitySelectionPage]):
    """Paginated read of an entity-kind selection.

    Page order is stable and lexicographic on the item IRI. The
    `(selection_name, item)` autoindex provides the ordering for free, so
    paginated reads avoid a temp-sort over the full selection.
    """

    selection: EntitySelectionName
    show: ShowFilter = ShowFilter.ALL

    @override
    def render(self) -> RenderedSql:
        """SQL for the main paginated page query.

        Count queries (total_filtered, present_count) are issued by `_run`; they
        are not part of the rendered statement.
        """
        sql_parts = [
            f"SELECT si.item, {_EXISTS_FRAGMENT} AS is_present",
            "FROM selection_items si",
            "WHERE si.selection_name = ?",
        ]
        params: list[object] = [self.selection.bare]

        filter_clause = _show_filter_clause(self.show)
        if filter_clause:
            sql_parts.append(filter_clause.lstrip())

        sql_parts.append("ORDER BY si.item")
        append_pagination(sql_parts, params, self.limit, self.offset)
        return RenderedSql(sql=" ".join(sql_parts), params=tuple(params))

    @override
    def _run(self, s: Session) -> EntitySelectionPage:
        name = self.selection.bare
        meta = get_selection(s, name)
        if meta.kind != SelectionKind.ENTITIES:
            raise SelectionKindMismatchError(name, SelectionKind.ENTITIES, meta.kind)

        filter_clause = _show_filter_clause(self.show)

        total_filtered = s.conn.execute(
            f"SELECT COUNT(*) FROM selection_items si WHERE si.selection_name = ?{filter_clause}",
            (name,),
        ).fetchone()[0]

        present_count = s.conn.execute(
            "SELECT COUNT(DISTINCT si.item) FROM selection_items si "
            "WHERE si.selection_name = ? "
            f"AND {_EXISTS_FRAGMENT}",
            (name,),
        ).fetchone()[0]

        compiled = self.render()
        rows = s.conn.execute(compiled.sql, compiled.params).fetchall()

        present_iris = [iri for iri, is_present in rows if is_present]
        roles_map: dict[str, EntityType] = {}
        labels_map: dict[str, str] = {}

        if present_iris:
            placeholders = ",".join("?" for _ in present_iris)
            roles_map.update(
                (iri, EntityType(role))
                for iri, role in s.conn.execute(
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
            show=self.show,
        )
