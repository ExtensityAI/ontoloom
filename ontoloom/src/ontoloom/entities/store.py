from collections import Counter, defaultdict

from ontoloom.connection import Session, escape_like
from ontoloom.entities.types import (
    AnnotationRow,
    DuplicateGroup,
    DuplicateResult,
    EntityInfo,
    EntityMatch,
    EntitySearchPage,
    EntitySummary,
    MatchQuality,
    MatchSource,
)
from ontoloom.errors import OntoloomError
from ontoloom.owl.axioms import Declaration
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.prefixes import PrefixName
from ontoloom.selections.store import get_selection
from ontoloom.selections.types import SelectionKind, SelectionName
from ontoloom.text_index import (
    DECLARED_EXISTS,
    DECLARED_NOT_EXISTS,
    LOCAL_NAME_PROPERTY,
    NOT_DEPRECATED,
)


class EntityNotFoundError(OntoloomError):
    """No entity with the given IRI exists in the ontology.

    `near_matches` are IRIs of entities with similar local names -> populated by
    `entities.get` so callers can show "did you mean…?" without re-querying.
    """

    def __init__(self, iri: str, near_matches: list[str] | None = None):
        self.iri = iri
        self.near_matches = near_matches or []
        super().__init__(f"Entity {iri!r} not found.")


# A: this file is huge. we need to look at it separately

_TEXT_SCAN_CAP = 1000


def _axiom_scope_join(s: Session, within: SelectionName | None) -> tuple[str, list[str]]:
    """Join clause for queries already in axiom-context (alias `a` for axioms).
    Silently no-op for ENTITIES selections -> these reads only respect axiom selections.
    """
    if within is None:
        return "", []
    sel = get_selection(s, within)
    if sel.kind != SelectionKind.AXIOMS:
        return "", []
    return (
        " JOIN selection_items si_w ON si_w.item = a.hash AND si_w.selection_name = ?",
        [within],
    )


def _entity_scope_join(s: Session, within: SelectionName | None) -> tuple[str, list[str]]:
    """Join clause for queries in axiom_entities-context (alias `ae`).
    Handles both AXIOMS (via a_w) and ENTITIES (via ae.entity_iri) selection kinds.
    """
    if within is None:
        return "", []
    sel = get_selection(s, within)
    if sel.kind == SelectionKind.ENTITIES:
        return (
            " JOIN selection_items si_w ON si_w.item = ae.entity_iri AND si_w.selection_name = ?",
            [within],
        )
    return (
        " JOIN axioms a_w ON a_w.id = ae.axiom_id"
        " JOIN selection_items si_w ON si_w.item = a_w.hash AND si_w.selection_name = ?",
        [within],
    )


def _entity_scope_allowed(s: Session, within: SelectionName) -> set[str]:
    """Allowed entity IRIs under `within`, as a set for in-Python post-filtering."""
    sel = get_selection(s, within)
    if sel.kind == SelectionKind.ENTITIES:
        return {
            r[0]
            for r in s._conn.execute(
                "SELECT item FROM selection_items WHERE selection_name = ?", (within,)
            )
        }
    return {
        r[0]
        for r in s._conn.execute(
            "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
            "JOIN axioms a ON a.id = ae.axiom_id "
            "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ?",
            (within,),
        )
    }


_NEAR_MATCH_LIMIT = 3


def get_entity(s: Session, iri: IRI, *, within: SelectionName | None = None) -> EntityInfo:
    """Return entity details. Raises EntityNotFoundError (with near matches) on miss."""
    iri_str = str(iri)

    roles = {
        EntityType(r[0])
        for r in s._conn.execute(
            "SELECT DISTINCT role FROM axiom_entities WHERE entity_iri = ? AND role IS NOT NULL",
            (iri_str,),
        )
    }

    annotations = [
        AnnotationRow(property=IRI(r[0]), value=r[1])
        for r in s._conn.execute(
            "SELECT DISTINCT property, text FROM entity_text "
            "WHERE entity_iri = ? AND property != ? "
            "ORDER BY property, text",
            (iri_str, LOCAL_NAME_PROPERTY),
        )
    ]

    extra_join, extra_params = _axiom_scope_join(s, within)

    axiom_counts = Counter(
        {
            r[0]: r[1]
            for r in s._conn.execute(
                f"""
            SELECT a.type, COUNT(DISTINCT a.id)
            FROM axiom_entities ae
            JOIN axioms a ON ae.axiom_id = a.id{extra_join}
            WHERE ae.entity_iri = ?
            GROUP BY a.type
            """,
                (*extra_params, iri_str),
            )
        }
    )

    if not roles and not annotations and not axiom_counts:
        near = search_entities(s, query=iri.local_name, limit=_NEAR_MATCH_LIMIT)
        raise EntityNotFoundError(iri_str, [str(m.iri) for m in near.matches])
    return EntityInfo(
        roles=frozenset(roles), annotations=tuple(annotations), axiom_counts=axiom_counts
    )


def axiom_hashes_for_entity(
    s: Session, iri: IRI, *, within: SelectionName | None = None
) -> list[str]:
    """Return all axiom hashes for an entity."""
    iri_str = str(iri)
    extra_join, extra_params = _axiom_scope_join(s, within)

    return [
        r[0]
        for r in s._conn.execute(
            f"SELECT DISTINCT a.hash FROM axiom_entities ae "
            f"JOIN axioms a ON ae.axiom_id = a.id{extra_join} "
            f"WHERE ae.entity_iri = ? ORDER BY a.hash",
            (*extra_params, iri_str),
        )
    ]


def search_entities(
    s: Session,
    *,
    query: str | None = None,
    role: EntityType | None = None,
    namespace: PrefixName | None = None,
    within: SelectionName | None = None,
    declared: bool | None = None,
    properties: list[IRI] | None = None,
    exclude_deprecated: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> EntitySearchPage:
    """Paginated entity search with optional filters.

    within: scope to a named selection. Entity selection restricts to those
    specific entities; axiom selection restricts to entities mentioned in those axioms.
    declared: True = only declared entities, False = only undeclared, None = all.
    properties: restrict text search to these annotation properties; when query is None,
    find entities that have any annotation with these properties.
    exclude_deprecated: exclude entities with owl:deprecated "true" annotation.
    """
    if query is None:
        return _list_entities(
            s,
            role=role,
            namespace=namespace,
            within=within,
            declared=declared,
            properties=properties,
            exclude_deprecated=exclude_deprecated,
            limit=limit,
            offset=offset,
        )
    return _text_search_entities(
        s,
        query=query,
        role=role,
        namespace=namespace,
        within=within,
        declared=declared,
        properties=properties,
        exclude_deprecated=exclude_deprecated,
        limit=limit,
        offset=offset,
    )


def collect_entity_iris(
    s: Session,
    *,
    query: str | None = None,
    role: EntityType | None = None,
    namespace: PrefixName | None = None,
    within: SelectionName | None = None,
    declared: bool | None = None,
    properties: list[IRI] | None = None,
    exclude_deprecated: bool = True,
) -> list[str]:
    """Return all matching entity IRIs (no display data). For select workflows."""
    if query is None:
        joins, where, params = _build_entity_filter(
            s, role, namespace, within, declared, properties, exclude_deprecated
        )
        return [
            r[0]
            for r in s._conn.execute(
                f"SELECT DISTINCT ae.entity_iri FROM axiom_entities ae{joins} "
                f"WHERE {where} ORDER BY ae.entity_iri",
                params,
            )
        ]

    # Text search path
    matches = _find_text_matches(s, query, LOCAL_NAME_PROPERTY, MatchSource.IRI, properties=None)
    matches.update(
        _find_text_matches(s, query, None, MatchSource.ANNOTATION, properties=properties)
    )
    matches = _apply_text_filters(s, matches, role, namespace, within, declared, exclude_deprecated)
    return list(matches.keys())


def entity_summary(s: Session, *, within: SelectionName | None = None) -> EntitySummary:
    if within is None:
        total = s._conn.execute("SELECT COUNT(DISTINCT entity_iri) FROM axiom_entities").fetchone()[
            0
        ]
        by_role = Counter(
            dict(
                s._conn.execute(
                    "SELECT role, COUNT(DISTINCT entity_iri) FROM axiom_entities WHERE role IS NOT NULL GROUP BY role"
                )
            )
        )
        return EntitySummary(total=total, by_role=by_role)

    sel = get_selection(s, within)
    if sel.kind == SelectionKind.ENTITIES:
        total = s._conn.execute(
            "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
            "JOIN selection_items si ON si.item = ae.entity_iri AND si.selection_name = ?",
            (within,),
        ).fetchone()[0]
        by_role = Counter(
            dict(
                s._conn.execute(
                    "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
                    "JOIN selection_items si ON si.item = ae.entity_iri AND si.selection_name = ? "
                    "WHERE ae.role IS NOT NULL GROUP BY ae.role",
                    (within,),
                )
            )
        )
    else:  # axioms
        total = s._conn.execute(
            "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
            "JOIN axioms a ON a.id = ae.axiom_id "
            "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ?",
            (within,),
        ).fetchone()[0]
        by_role = Counter(
            dict(
                s._conn.execute(
                    "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
                    "JOIN axioms a ON a.id = ae.axiom_id "
                    "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
                    "WHERE ae.role IS NOT NULL GROUP BY ae.role",
                    (within,),
                )
            )
        )
    return EntitySummary(total=total, by_role=by_role)


def find_duplicate_entities(
    s: Session,
    annotation_property: IRI,
    *,
    within: SelectionName | None = None,
) -> DuplicateResult:
    """Find annotation values shared by multiple entities."""
    sel_join_outer = ""
    sel_join_inner = ""
    sel_params: list[str] = []
    if within is not None:
        get_selection(s, within)  # validates existence; matches other read entrypoints
        sel_join_outer = (
            " JOIN selection_items si ON si.item = et.entity_iri AND si.selection_name = ?"
        )
        sel_join_inner = (
            " JOIN selection_items si2 ON si2.item = et2.entity_iri AND si2.selection_name = ?"
        )
        sel_params.append(within)

    # EXISTS variant of the previous CTE: for each (text, iri) row in the
    # property/scope, keep it iff some *other* entity has the same text.
    # Lets SQLite use idx_entity_text_prop_text directly without a temp table.
    rows = s._conn.execute(
        f"SELECT et.text, et.entity_iri"
        f" FROM entity_text et{sel_join_outer}"
        f" WHERE et.property = ?"
        f"   AND EXISTS ("
        f"     SELECT 1 FROM entity_text et2{sel_join_inner}"
        f"     WHERE et2.property = ? AND et2.text = et.text AND et2.entity_iri != et.entity_iri"
        f"   )"
        f" GROUP BY et.text, et.entity_iri"
        f" ORDER BY et.text, et.entity_iri",
        (*sel_params, annotation_property, *sel_params, annotation_property),
    ).fetchall()

    by_text: dict[str, list[str]] = defaultdict(list)
    for text, iri in rows:
        by_text[text].append(iri)

    sorted_pairs = sorted(by_text.items(), key=lambda g: len(g[1]), reverse=True)
    groups = tuple(DuplicateGroup(value=value, iris=tuple(iris)) for value, iris in sorted_pairs)
    affected: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for iri in group.iris:
            if iri not in seen:
                seen.add(iri)
                affected.append(iri)

    return DuplicateResult(
        groups=groups,
        total_groups=len(groups),
        affected_iris=tuple(affected),
    )


# -- Private helpers --


def _build_entity_filter(
    s: Session,
    role: EntityType | None,
    namespace: PrefixName | None,
    within: SelectionName | None,
    declared: bool | None,
    properties: list[IRI] | None,
    exclude_deprecated: bool,
) -> tuple[str, str, list[str | int]]:
    """Build (joins, where_clause, params) for entity queries against `axiom_entities ae`."""
    conditions = ["ae.role IS NOT NULL"]
    joins, scope_params = _entity_scope_join(s, within)
    params: list[str | int] = list(scope_params)

    if role is not None:
        conditions.append("ae.role = ?")
        params.append(role)
    if namespace is not None:
        conditions.append("ae.entity_iri LIKE ? || ':%' ESCAPE '\\'")
        params.append(escape_like(namespace))

    if declared is True:
        conditions.append(DECLARED_EXISTS)
    elif declared is False:
        conditions.append(DECLARED_NOT_EXISTS)

    if properties is not None:
        ph = ",".join("?" for _ in properties)
        conditions.append(
            f"EXISTS (SELECT 1 FROM entity_text et_p WHERE et_p.entity_iri = ae.entity_iri AND et_p.property IN ({ph}))"
        )
        params.extend(properties)

    if exclude_deprecated:
        conditions.append(NOT_DEPRECATED)

    return joins, " AND ".join(conditions), params


def _apply_text_filters(
    s: Session,
    matches: dict[str, tuple[MatchSource, MatchQuality]],
    role: EntityType | None,
    namespace: PrefixName | None,
    within: SelectionName | None,
    declared: bool | None,
    exclude_deprecated: bool,
) -> dict[str, tuple[MatchSource, MatchQuality]]:
    """Apply post-text-search filters to candidate matches."""
    if within is not None and matches:
        allowed = _entity_scope_allowed(s, within)
        matches = {k: v for k, v in matches.items() if k in allowed}

    if role is not None and matches:
        role_iris = _batch_check_roles(s, list(matches.keys()), role)
        matches = {k: v for k, v in matches.items() if k in role_iris}
    if namespace is not None:
        prefix = f"{namespace}:"
        matches = {k: v for k, v in matches.items() if k.startswith(prefix)}

    if declared is not None and matches:
        matches = _filter_declared(s, matches, declared)
    if exclude_deprecated and matches:
        matches = _filter_deprecated(s, matches)

    return matches


def _list_entities(
    s: Session,
    role: EntityType | None,
    namespace: PrefixName | None,
    within: SelectionName | None,
    declared: bool | None,
    properties: list[IRI] | None,
    exclude_deprecated: bool,
    limit: int,
    offset: int,
) -> EntitySearchPage:
    joins, where, params = _build_entity_filter(
        s, role, namespace, within, declared, properties, exclude_deprecated
    )

    total = s._conn.execute(
        f"SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae{joins} WHERE {where}",
        params,
    ).fetchone()[0]

    page_iris = [
        r[0]
        for r in s._conn.execute(
            f"SELECT DISTINCT ae.entity_iri FROM axiom_entities ae{joins} WHERE {where} ORDER BY ae.entity_iri LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
    ]
    if not page_iris:
        return EntitySearchPage(matches=(), total=total, offset=offset)

    display = _batch_fetch_entity_display(s, page_iris)
    return EntitySearchPage(
        matches=tuple(
            EntityMatch(
                iri=IRI(iri_str),
                roles=display.get(iri_str, (frozenset(), ()))[0],
                annotations=display.get(iri_str, (frozenset(), ()))[1],
                match_source=MatchSource.LIST,
                match_quality=MatchQuality.EXACT,
            )
            for iri_str in page_iris
        ),
        total=total,
        offset=offset,
    )


def _text_search_entities(
    s: Session,
    query: str,
    role: EntityType | None,
    namespace: PrefixName | None,
    within: SelectionName | None,
    declared: bool | None,
    properties: list[IRI] | None,
    exclude_deprecated: bool,
    limit: int,
    offset: int,
) -> EntitySearchPage:
    matches = _find_text_matches(s, query, LOCAL_NAME_PROPERTY, MatchSource.IRI, properties=None)
    matches.update(
        _find_text_matches(s, query, None, MatchSource.ANNOTATION, properties=properties)
    )
    matches = _apply_text_filters(s, matches, role, namespace, within, declared, exclude_deprecated)

    quality_order = {MatchQuality.EXACT: 0, MatchQuality.SUBSTRING: 1}
    source_order = {MatchSource.IRI: 0, MatchSource.ANNOTATION: 1}
    sorted_iris = sorted(
        matches.keys(),
        key=lambda k: (
            quality_order.get(matches[k][1], 9),
            source_order.get(matches[k][0], 9),
            k,
        ),
    )

    total = len(sorted_iris)
    page_iris = sorted_iris[offset : offset + limit]
    if not page_iris:
        return EntitySearchPage(matches=(), total=total, offset=offset)

    display = _batch_fetch_entity_display(s, page_iris)
    return EntitySearchPage(
        matches=tuple(
            EntityMatch(
                iri=IRI(iri_str),
                roles=display.get(iri_str, (frozenset(), ()))[0],
                annotations=display.get(iri_str, (frozenset(), ()))[1],
                match_source=matches[iri_str][0],
                match_quality=matches[iri_str][1],
            )
            for iri_str in page_iris
        ),
        total=total,
        offset=offset,
    )


def _batch_fetch_entity_display(s: Session, iris: list[str]):
    placeholders = ",".join("?" for _ in iris)

    roles_by_iri: dict[str, set[EntityType]] = {}
    for iri_str, role_val in s._conn.execute(
        f"SELECT entity_iri, role FROM axiom_entities WHERE entity_iri IN ({placeholders}) AND role IS NOT NULL",
        iris,
    ):
        roles_by_iri.setdefault(iri_str, set()).add(EntityType(role_val))

    anns_by_iri: dict[str, list[AnnotationRow]] = {}
    for iri_str, prop, text in s._conn.execute(
        f"SELECT DISTINCT entity_iri, property, text FROM entity_text "
        f"WHERE entity_iri IN ({placeholders}) AND property != ? "
        f"ORDER BY entity_iri, property, text",
        [*iris, LOCAL_NAME_PROPERTY],
    ):
        anns_by_iri.setdefault(iri_str, []).append(AnnotationRow(property=IRI(prop), value=text))

    return {
        iri_str: (
            frozenset(roles_by_iri.get(iri_str, ())),
            tuple(anns_by_iri.get(iri_str, ())),
        )
        for iri_str in iris
    }


def _batch_check_roles(s: Session, iris: list[str], role: EntityType) -> set[str]:
    placeholders = ",".join("?" for _ in iris)
    return {
        r[0]
        for r in s._conn.execute(
            f"SELECT DISTINCT entity_iri FROM axiom_entities WHERE entity_iri IN ({placeholders}) AND role = ?",
            [*iris, role],
        )
    }


def _filter_declared(
    s: Session,
    matches: dict[str, tuple[MatchSource, MatchQuality]],
    declared: bool,
) -> dict[str, tuple[MatchSource, MatchQuality]]:
    """Filter text-search matches by declaration status."""
    iris = list(matches.keys())
    placeholders = ",".join("?" for _ in iris)
    declared_iris = {
        r[0]
        for r in s._conn.execute(
            f"SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
            f"JOIN axioms a ON a.id = ae.axiom_id "
            f"WHERE ae.entity_iri IN ({placeholders}) AND a.type = '{Declaration.tag()}'",
            iris,
        )
    }
    if declared:
        return {k: v for k, v in matches.items() if k in declared_iris}
    return {k: v for k, v in matches.items() if k not in declared_iris}


def _filter_deprecated(
    s: Session,
    matches: dict[str, tuple[MatchSource, MatchQuality]],
) -> dict[str, tuple[MatchSource, MatchQuality]]:
    """Remove deprecated entities from text-search matches."""
    iris = list(matches.keys())
    placeholders = ",".join("?" for _ in iris)
    deprecated_iris = {
        r[0]
        for r in s._conn.execute(
            f"SELECT DISTINCT entity_iri FROM entity_text "
            f"WHERE entity_iri IN ({placeholders}) "
            f"AND property LIKE '%deprecated%' AND LOWER(text) = 'true'",
            iris,
        )
    }
    return {k: v for k, v in matches.items() if k not in deprecated_iris}


def _find_text_matches(
    s: Session,
    query: str,
    property_filter: str | None,
    source_label: MatchSource,
    *,
    properties: list[IRI] | None = None,
) -> dict[str, tuple[MatchSource, MatchQuality]]:
    """Returns {iri: (source_label, quality)}.

    properties: when set, restrict annotation search to these property IRIs.
    Only applies when property_filter is None (annotation search path).
    """
    params: list[str] = []
    if property_filter is not None:
        prop_cond = "property = ?"
        params.append(property_filter)
    elif properties is not None:
        ph = ",".join("?" for _ in properties)
        prop_cond = f"property IN ({ph})"
        params.extend(properties)
    else:
        prop_cond = "property != ?"
        params.append(LOCAL_NAME_PROPERTY)

    # ORDER BY entity_iri: insertion order determines `_text_search_entities`
    # pagination output. Without it, page-1 contents drift across runs.
    # LIMIT _TEXT_SCAN_CAP: bound memory for runaway substring queries; user
    # sees first-N alphabetical IRIs rather than all matches.
    matches: dict[str, tuple[MatchSource, MatchQuality]] = {}
    query_lower = query.lower()

    for (iri_str,) in s._conn.execute(
        f"SELECT DISTINCT entity_iri FROM entity_text WHERE {prop_cond} AND LOWER(text) = ? ORDER BY entity_iri LIMIT ?",
        [*params, query_lower, _TEXT_SCAN_CAP],
    ):
        if iri_str not in matches:
            matches[iri_str] = (source_label, MatchQuality.EXACT)

    for (iri_str,) in s._conn.execute(
        f"SELECT DISTINCT entity_iri FROM entity_text WHERE {prop_cond} AND INSTR(LOWER(text), ?) > 0 ORDER BY entity_iri LIMIT ?",
        [*params, query_lower, _TEXT_SCAN_CAP],
    ):
        if iri_str not in matches:
            matches[iri_str] = (source_label, MatchQuality.SUBSTRING)

    return matches


def top_entities_by_axiom_count(s: Session, n: int) -> list[tuple[IRI, int]]:
    """Top n entities by number of distinct axioms they appear in."""
    return [
        (IRI(row[0]), row[1])
        for row in s._conn.execute(
            "SELECT ae.entity_iri, COUNT(DISTINCT ae.axiom_id) AS cnt "
            "FROM axiom_entities ae "
            "GROUP BY ae.entity_iri "
            "ORDER BY cnt DESC "
            "LIMIT ?",
            (n,),
        ).fetchall()
    ]


def undeclared_entity_count(
    s: Session,
    within: SelectionName | None = None,
    *,
    exclude_deprecated: bool = True,
) -> int:
    """Count distinct entities that lack a Declaration axiom.

    `exclude_deprecated=True` matches `search_entities(declared=False)` defaults.
    Set False to count every undeclared entity including deprecated ones.
    """
    scope_join, scope_params = _entity_scope_join(s, within)
    where = DECLARED_NOT_EXISTS
    if exclude_deprecated:
        where = f"{where} AND {NOT_DEPRECATED}"
    return s._conn.execute(
        f"SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae{scope_join} WHERE {where}",
        scope_params,
    ).fetchone()[0]
