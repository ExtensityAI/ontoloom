from collections import Counter, defaultdict

from ontoloom.ontology import selections
from ontoloom.ontology.connection import Ontology, escape_like
from ontoloom.ontology.models.literals import IRI, EntityType
from ontoloom.ontology.types import (
    AnnotationRow,
    DuplicateResult,
    EntityInfo,
    EntityMatch,
    EntitySearchPage,
    SelectionKind,
)

_LOCAL_NAME = "local_name"

# SQL fragments for declared/deprecated filters (reference ae.entity_iri from outer query)
_DECLARED_EXISTS = (
    "EXISTS (SELECT 1 FROM axiom_entities ae_d "
    "JOIN axioms a_d ON a_d.id = ae_d.axiom_id "
    "WHERE ae_d.entity_iri = ae.entity_iri AND a_d.type = 'Declaration')"
)
_DECLARED_NOT_EXISTS = (
    "NOT EXISTS (SELECT 1 FROM axiom_entities ae_d "
    "JOIN axioms a_d ON a_d.id = ae_d.axiom_id "
    "WHERE ae_d.entity_iri = ae.entity_iri AND a_d.type = 'Declaration')"
)
_NOT_DEPRECATED = (
    "NOT EXISTS (SELECT 1 FROM entity_text et_dep "
    "WHERE et_dep.entity_iri = ae.entity_iri "
    "AND et_dep.property LIKE '%deprecated%' AND LOWER(et_dep.text) = 'true')"
)


def _axiom_scope_join(ont: Ontology, within: str | None) -> tuple[str, list[str]]:
    """Join clause for queries already in axiom-context (alias `a` for axioms).
    Silently no-op for ENTITIES selections — these reads only respect axiom selections.
    """
    if within is None:
        return "", []
    sel = selections.get_info(ont, within)
    if sel.kind != SelectionKind.AXIOMS:
        return "", []
    return (
        " JOIN selection_items si_w ON si_w.item = a.hash AND si_w.selection_name = ?",
        [within],
    )


def _entity_scope_join(ont: Ontology, within: str | None) -> tuple[str, list[str]]:
    """Join clause for queries in axiom_entities-context (alias `ae`).
    Handles both AXIOMS (via a_w) and ENTITIES (via ae.entity_iri) selection kinds.
    """
    if within is None:
        return "", []
    sel = selections.get_info(ont, within)
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


def _entity_scope_allowed(ont: Ontology, within: str) -> set[str]:
    """Allowed entity IRIs under `within`, as a set for in-Python post-filtering."""
    sel = selections.get_info(ont, within)
    if sel.kind == SelectionKind.ENTITIES:
        return {
            r[0]
            for r in ont.conn.execute(
                "SELECT item FROM selection_items WHERE selection_name = ?", (within,)
            )
        }
    return {
        r[0]
        for r in ont.conn.execute(
            "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
            "JOIN axioms a ON a.id = ae.axiom_id "
            "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ?",
            (within,),
        )
    }


def get(ont: Ontology, iri: IRI, *, within: str | None = None) -> EntityInfo | None:
    iri_str = str(iri)

    roles = {
        EntityType(r[0])
        for r in ont.conn.execute(
            "SELECT DISTINCT role FROM axiom_entities WHERE entity_iri = ? AND role IS NOT NULL",
            (iri_str,),
        )
    }

    annotations = [
        AnnotationRow(property=IRI(r[0]), value=r[1])
        for r in ont.conn.execute(
            "SELECT DISTINCT property, text FROM entity_text WHERE entity_iri = ? AND property != ?",
            (iri_str, _LOCAL_NAME),
        )
    ]

    extra_join, extra_params = _axiom_scope_join(ont, within)

    axiom_counts = Counter(
        {
            r[0]: r[1]
            for r in ont.conn.execute(
                f"""
            SELECT a.type, COUNT(DISTINCT a.id)
            FROM axiom_entities ae
            JOIN axioms a ON ae.axiom_id = a.id{extra_join}
            WHERE ae.entity_iri = ? AND a.type != 'AnnotationAssertion'
            GROUP BY a.type
            """,
                (*extra_params, iri_str),
            )
        }
    )

    if not roles and not annotations and not axiom_counts:
        return None
    return EntityInfo(roles=roles, annotations=annotations, axiom_counts=axiom_counts)


def get_axiom_hashes(ont: Ontology, iri: IRI, *, within: str | None = None) -> list[str]:
    """Return all axiom hashes for an entity."""
    iri_str = str(iri)
    extra_join, extra_params = _axiom_scope_join(ont, within)

    return [
        r[0]
        for r in ont.conn.execute(
            f"SELECT DISTINCT a.hash FROM axiom_entities ae "
            f"JOIN axioms a ON ae.axiom_id = a.id{extra_join} "
            f"WHERE ae.entity_iri = ?",
            (*extra_params, iri_str),
        )
    ]


def search(
    ont: Ontology,
    *,
    query: str | None = None,
    role: str | None = None,
    namespace: str | None = None,
    within: str | None = None,
    declared: bool | None = None,
    properties: list[str] | None = None,
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
            ont,
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
        ont,
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


def collect_iris(  # noqa: C901
    ont: Ontology,
    *,
    query: str | None = None,
    role: str | None = None,
    namespace: str | None = None,
    within: str | None = None,
    declared: bool | None = None,
    properties: list[str] | None = None,
    exclude_deprecated: bool = True,
) -> list[str]:
    """Return all matching entity IRIs (no display data). For select workflows."""
    if query is None:
        conditions = ["ae.role IS NOT NULL"]
        joins, scope_params = _entity_scope_join(ont, within)
        params: list[str | int] = list(scope_params)

        if role is not None:
            conditions.append("ae.role = ?")
            params.append(role)
        if namespace is not None:
            conditions.append("ae.entity_iri LIKE ? || ':%' ESCAPE '\\'")
            params.append(escape_like(namespace))

        if declared is True:
            conditions.append(_DECLARED_EXISTS)
        elif declared is False:
            conditions.append(_DECLARED_NOT_EXISTS)

        if properties is not None:
            ph = ",".join("?" for _ in properties)
            conditions.append(
                f"EXISTS (SELECT 1 FROM entity_text et_p WHERE et_p.entity_iri = ae.entity_iri AND et_p.property IN ({ph}))"
            )
            params.extend(properties)

        if exclude_deprecated:
            conditions.append(_NOT_DEPRECATED)

        where = " AND ".join(conditions)
        return [
            r[0]
            for r in ont.conn.execute(
                f"SELECT DISTINCT ae.entity_iri FROM axiom_entities ae{joins} WHERE {where}",
                params,
            )
        ]

    # Text search path
    matches = _find_text_matches(ont, query, _LOCAL_NAME, "iri", properties=None)
    matches.update(_find_text_matches(ont, query, None, "annotation", properties=properties))

    if within is not None and matches:
        allowed = _entity_scope_allowed(ont, within)
        matches = {k: v for k, v in matches.items() if k in allowed}

    if role is not None and matches:
        role_iris = _batch_check_roles(ont, list(matches.keys()), role)
        matches = {k: v for k, v in matches.items() if k in role_iris}
    if namespace is not None:
        prefix = f"{namespace}:"
        matches = {k: v for k, v in matches.items() if k.startswith(prefix)}

    if declared is not None and matches:
        matches = _filter_declared(ont, matches, declared)
    if exclude_deprecated and matches:
        matches = _filter_deprecated(ont, matches)

    return list(matches.keys())


def summary(ont: Ontology, *, within: str | None = None) -> tuple[int, Counter[str]]:
    if within is None:
        total = ont.conn.execute(
            "SELECT COUNT(DISTINCT entity_iri) FROM axiom_entities"
        ).fetchone()[0]
        role_counts = Counter(
            {
                r[0]: r[1]
                for r in ont.conn.execute(
                    "SELECT role, COUNT(DISTINCT entity_iri) FROM axiom_entities WHERE role IS NOT NULL GROUP BY role"
                )
            }
        )
        return total, role_counts

    sel = selections.get_info(ont, within)
    if sel.kind == SelectionKind.ENTITIES:
        total = ont.conn.execute(
            "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
            "JOIN selection_items si ON si.item = ae.entity_iri AND si.selection_name = ?",
            (within,),
        ).fetchone()[0]
        role_counts = Counter(
            {
                r[0]: r[1]
                for r in ont.conn.execute(
                    "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
                    "JOIN selection_items si ON si.item = ae.entity_iri AND si.selection_name = ? "
                    "WHERE ae.role IS NOT NULL GROUP BY ae.role",
                    (within,),
                )
            }
        )
    else:  # axioms
        total = ont.conn.execute(
            "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
            "JOIN axioms a ON a.id = ae.axiom_id "
            "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ?",
            (within,),
        ).fetchone()[0]
        role_counts = Counter(
            {
                r[0]: r[1]
                for r in ont.conn.execute(
                    "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
                    "JOIN axioms a ON a.id = ae.axiom_id "
                    "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
                    "WHERE ae.role IS NOT NULL GROUP BY ae.role",
                    (within,),
                )
            }
        )
    return total, role_counts


def find_duplicates(
    ont: Ontology,
    annotation_property: str,
    *,
    within: str | None = None,
) -> DuplicateResult:
    """Find annotation values shared by multiple entities."""
    sel_join = ""
    sel_params: list[str] = []
    if within is not None:
        sel_join = " JOIN selection_items si ON si.item = et.entity_iri AND si.selection_name = ?"
        sel_params.append(within)

    rows = ont.conn.execute(
        f"WITH dupe_texts AS ("
        f"  SELECT text FROM entity_text et{sel_join}"
        f"  WHERE et.property = ? GROUP BY text"
        f"  HAVING COUNT(DISTINCT et.entity_iri) > 1"
        f") "
        f"SELECT et.text, et.entity_iri"
        f" FROM entity_text et"
        f"{sel_join}"
        f" JOIN dupe_texts dt ON dt.text = et.text"
        f" WHERE et.property = ?"
        f" GROUP BY et.text, et.entity_iri"
        f" ORDER BY et.text, et.entity_iri",
        (*sel_params, annotation_property, *sel_params, annotation_property),
    ).fetchall()

    by_text: dict[str, list[str]] = defaultdict(list)
    for text, iri in rows:
        by_text[text].append(iri)

    groups = sorted(by_text.items(), key=lambda g: len(g[1]), reverse=True)
    affected: list[str] = []
    seen: set[str] = set()
    for _, iris in groups:
        for iri in iris:
            if iri not in seen:
                seen.add(iri)
                affected.append(iri)

    return DuplicateResult(
        groups=groups,
        total_groups=len(groups),
        affected_iris=affected,
    )


# -- Private helpers --


def _list_entities(
    ont: Ontology,
    role: str | None,
    namespace: str | None,
    within: str | None,
    declared: bool | None,
    properties: list[str] | None,
    exclude_deprecated: bool,
    limit: int,
    offset: int,
) -> EntitySearchPage:
    conditions = ["ae.role IS NOT NULL"]
    joins, scope_params = _entity_scope_join(ont, within)
    params: list[str | int] = list(scope_params)

    if role is not None:
        conditions.append("ae.role = ?")
        params.append(role)
    if namespace is not None:
        conditions.append("ae.entity_iri LIKE ? || ':%' ESCAPE '\\'")
        params.append(escape_like(namespace))

    if declared is True:
        conditions.append(_DECLARED_EXISTS)
    elif declared is False:
        conditions.append(_DECLARED_NOT_EXISTS)

    if properties is not None:
        ph = ",".join("?" for _ in properties)
        conditions.append(
            f"EXISTS (SELECT 1 FROM entity_text et_p WHERE et_p.entity_iri = ae.entity_iri AND et_p.property IN ({ph}))"
        )
        params.extend(properties)

    if exclude_deprecated:
        conditions.append(_NOT_DEPRECATED)

    where = " AND ".join(conditions)

    total = ont.conn.execute(
        f"SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae{joins} WHERE {where}",
        params,
    ).fetchone()[0]

    page_iris = [
        r[0]
        for r in ont.conn.execute(
            f"SELECT DISTINCT ae.entity_iri FROM axiom_entities ae{joins} WHERE {where} ORDER BY ae.entity_iri LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
    ]
    if not page_iris:
        return EntitySearchPage(matches=[], total=total)

    display = _batch_fetch_entity_display(ont, page_iris)
    return EntitySearchPage(
        matches=[
            EntityMatch(
                iri=IRI(iri_str),
                roles=display.get(iri_str, (set(), []))[0],
                annotations=display.get(iri_str, (set(), []))[1],
                match_source="list",
                match_quality="exact",
            )
            for iri_str in page_iris
        ],
        total=total,
    )


def _text_search_entities(
    ont: Ontology,
    query: str,
    role: str | None,
    namespace: str | None,
    within: str | None,
    declared: bool | None,
    properties: list[str] | None,
    exclude_deprecated: bool,
    limit: int,
    offset: int,
) -> EntitySearchPage:
    matches = _find_text_matches(ont, query, _LOCAL_NAME, "iri", properties=None)
    matches.update(_find_text_matches(ont, query, None, "annotation", properties=properties))

    if within is not None and matches:
        allowed = _entity_scope_allowed(ont, within)
        matches = {k: v for k, v in matches.items() if k in allowed}

    if role is not None and matches:
        role_iris = _batch_check_roles(ont, list(matches.keys()), role)
        matches = {k: v for k, v in matches.items() if k in role_iris}
    if namespace is not None:
        prefix = f"{namespace}:"
        matches = {k: v for k, v in matches.items() if k.startswith(prefix)}

    if declared is not None and matches:
        matches = _filter_declared(ont, matches, declared)
    if exclude_deprecated and matches:
        matches = _filter_deprecated(ont, matches)

    quality_order = {"exact": 0, "substring": 1}
    source_order = {"iri": 0, "annotation": 1}
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
        return EntitySearchPage(matches=[], total=total)

    display = _batch_fetch_entity_display(ont, page_iris)
    return EntitySearchPage(
        matches=[
            EntityMatch(
                iri=IRI(iri_str),
                roles=display.get(iri_str, (set(), []))[0],
                annotations=display.get(iri_str, (set(), []))[1],
                match_source=matches[iri_str][0],
                match_quality=matches[iri_str][1],
            )
            for iri_str in page_iris
        ],
        total=total,
    )


def _batch_fetch_entity_display(ont: Ontology, iris: list[str]):
    placeholders = ",".join("?" for _ in iris)

    roles_by_iri: dict[str, set[EntityType]] = {}
    for iri_str, role_val in ont.conn.execute(
        f"SELECT entity_iri, role FROM axiom_entities WHERE entity_iri IN ({placeholders}) AND role IS NOT NULL",
        iris,
    ):
        roles_by_iri.setdefault(iri_str, set()).add(EntityType(role_val))

    anns_by_iri: dict[str, list[AnnotationRow]] = {}
    for iri_str, prop, text in ont.conn.execute(
        f"SELECT DISTINCT entity_iri, property, text FROM entity_text WHERE entity_iri IN ({placeholders}) AND property != ?",
        [*iris, _LOCAL_NAME],
    ):
        anns_by_iri.setdefault(iri_str, []).append(AnnotationRow(property=IRI(prop), value=text))

    return {
        iri_str: (roles_by_iri.get(iri_str, set()), anns_by_iri.get(iri_str, []))
        for iri_str in iris
    }


def _batch_check_roles(ont: Ontology, iris: list[str], role: str) -> set[str]:
    placeholders = ",".join("?" for _ in iris)
    return {
        r[0]
        for r in ont.conn.execute(
            f"SELECT DISTINCT entity_iri FROM axiom_entities WHERE entity_iri IN ({placeholders}) AND role = ?",
            [*iris, role],
        )
    }


def _filter_declared(
    ont: Ontology,
    matches: dict[str, tuple[str, str]],
    declared: bool,
) -> dict[str, tuple[str, str]]:
    """Filter text-search matches by declaration status."""
    iris = list(matches.keys())
    placeholders = ",".join("?" for _ in iris)
    declared_iris = {
        r[0]
        for r in ont.conn.execute(
            f"SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
            f"JOIN axioms a ON a.id = ae.axiom_id "
            f"WHERE ae.entity_iri IN ({placeholders}) AND a.type = 'Declaration'",
            iris,
        )
    }
    if declared:
        return {k: v for k, v in matches.items() if k in declared_iris}
    return {k: v for k, v in matches.items() if k not in declared_iris}


def _filter_deprecated(
    ont: Ontology,
    matches: dict[str, tuple[str, str]],
) -> dict[str, tuple[str, str]]:
    """Remove deprecated entities from text-search matches."""
    iris = list(matches.keys())
    placeholders = ",".join("?" for _ in iris)
    deprecated_iris = {
        r[0]
        for r in ont.conn.execute(
            f"SELECT DISTINCT entity_iri FROM entity_text "
            f"WHERE entity_iri IN ({placeholders}) "
            f"AND property LIKE '%deprecated%' AND LOWER(text) = 'true'",
            iris,
        )
    }
    return {k: v for k, v in matches.items() if k not in deprecated_iris}


def _find_text_matches(
    ont: Ontology,
    query: str,
    property_filter: str | None,
    source_label: str,
    *,
    properties: list[str] | None = None,
) -> dict[str, tuple[str, str]]:
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
        params.append(_LOCAL_NAME)

    matches: dict[str, tuple[str, str]] = {}
    query_lower = query.lower()

    for (iri_str,) in ont.conn.execute(
        f"SELECT DISTINCT entity_iri FROM entity_text WHERE {prop_cond} AND LOWER(text) = ?",
        [*params, query_lower],
    ):
        if iri_str not in matches:
            matches[iri_str] = (source_label, "exact")

    for (iri_str,) in ont.conn.execute(
        f"SELECT DISTINCT entity_iri FROM entity_text WHERE {prop_cond} AND INSTR(LOWER(text), ?) > 0",
        [*params, query_lower],
    ):
        if iri_str not in matches:
            matches[iri_str] = (source_label, "substring")

    return matches
