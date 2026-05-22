"""Find annotation values shared by more than one entity, optionally scoped to a selection."""

from collections import defaultdict
from typing import override

from ontoloom.connection import Session
from ontoloom.entities.types import DuplicateGroup, DuplicateResult
from ontoloom.owl.iri import IRI
from ontoloom.query.base import Query, RenderedSql
from ontoloom.selections.store import get_selection
from ontoloom.selections.types import EntitySelectionName


class FindDuplicateEntities(Query[DuplicateResult]):
    """Caller-side use of `affected_iris` covers the full result set; no pagination."""

    annotation_property: IRI
    within: EntitySelectionName | None = None

    @override
    def render(self) -> RenderedSql:
        if self.within is None:
            scope_outer = ""
            scope_inner = ""
            params: tuple[object, ...] = (self.annotation_property, self.annotation_property)
        else:
            scope_outer = (
                " AND EXISTS (SELECT 1 FROM selection_items si"
                " WHERE si.item = et.entity_iri AND si.selection_name = ?)"
            )
            scope_inner = (
                " AND EXISTS (SELECT 1 FROM selection_items si2"
                " WHERE si2.item = et2.entity_iri AND si2.selection_name = ?)"
            )
            params = (
                self.annotation_property,
                self.within.bare,
                self.annotation_property,
                self.within.bare,
            )

        sql = (
            "SELECT et.text, et.entity_iri"
            " FROM entity_text et"
            f" WHERE et.property = ?{scope_outer}"
            "   AND EXISTS ("
            "     SELECT 1 FROM entity_text et2"
            f"     WHERE et2.property = ? AND et2.text = et.text AND et2.entity_iri != et.entity_iri{scope_inner}"
            "   )"
            " GROUP BY et.text, et.entity_iri"
            " ORDER BY et.text, et.entity_iri"
        )

        return RenderedSql(sql=sql, params=params)

    @override
    def _run(self, s: Session) -> DuplicateResult:
        if self.within is not None:
            get_selection(s, self.within.bare)  # raises SelectionNotFoundError if absent

        compiled = self.render()
        rows = s.conn.execute(compiled.sql, compiled.params).fetchall()

        by_text: dict[str, list[str]] = defaultdict(list)
        for text, iri in rows:
            by_text[text].append(iri)

        sorted_pairs = sorted(by_text.items(), key=lambda g: len(g[1]), reverse=True)
        groups = tuple(
            DuplicateGroup(value=value, iris=tuple(iris)) for value, iris in sorted_pairs
        )
        affected = tuple(dict.fromkeys(iri for group in groups for iri in group.iris))

        return DuplicateResult(
            groups=groups,
            total_groups=len(groups),
            affected_iris=affected,
        )
