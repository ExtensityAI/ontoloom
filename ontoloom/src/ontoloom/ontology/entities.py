from collections import Counter

from ontoloom.ontology import selections
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.models.base import EntityType
from ontoloom.ontology.models.literals import IRI
from ontoloom.ontology.types import (
    AnnotationRow,
    EntityInfo,
    EntityMatch,
    EntitySearchPage,
    SelectionKind,
)

_LOCAL_NAME = "local_name"


def get(ont: Ontology, iri: IRI, *, within_selection: str | None = None) -> EntityInfo | None:
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

    extra_join = ""
    extra_params: list[str] = []
    if within_selection is not None:
        sel = selections.get_info(ont, within_selection)
        if sel.kind == SelectionKind.AXIOMS:
            extra_join = (
                " JOIN selection_items si_w ON si_w.item = a.hash AND si_w.selection_name = ?"
            )
            extra_params.append(within_selection)

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


def get_axiom_hashes(ont: Ontology, iri: IRI, *, within_selection: str | None = None) -> list[str]:
    """Return all axiom hashes for an entity."""
    iri_str = str(iri)
    extra_join = ""
    extra_params: list[str] = []
    if within_selection is not None:
        sel = selections.get_info(ont, within_selection)
        if sel.kind == SelectionKind.AXIOMS:
            extra_join = (
                " JOIN selection_items si_w ON si_w.item = a.hash AND si_w.selection_name = ?"
            )
            extra_params.append(within_selection)

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
    within_selection: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> EntitySearchPage:
    """Paginated entity search with optional filters.

    within_selection: scope to a named selection. Entity selection restricts to those
    specific entities; axiom selection restricts to entities mentioned in those axioms.
    """
    if query is None:
        return _list_entities(
            ont,
            role=role,
            namespace=namespace,
            within_selection=within_selection,
            limit=limit,
            offset=offset,
        )
    return _text_search_entities(
        ont,
        query=query,
        role=role,
        namespace=namespace,
        within_selection=within_selection,
        limit=limit,
        offset=offset,
    )


def collect_iris(
    ont: Ontology,
    *,
    query: str | None = None,
    role: str | None = None,
    namespace: str | None = None,
    within_selection: str | None = None,
) -> list[str]:
    """Return all matching entity IRIs (no display data). For select workflows."""
    if query is None:
        conditions = ["ae.role IS NOT NULL"]
        params: list[str | int] = []
        joins = ""

        if within_selection is not None:
            sel = selections.get_info(ont, within_selection)
            if sel.kind == SelectionKind.ENTITIES:
                joins = " JOIN selection_items si_w ON si_w.item = ae.entity_iri AND si_w.selection_name = ?"
                params.append(within_selection)
            else:
                joins = (
                    " JOIN axioms a_w ON a_w.id = ae.axiom_id"
                    " JOIN selection_items si_w ON si_w.item = a_w.hash AND si_w.selection_name = ?"
                )
                params.append(within_selection)

        if role is not None:
            conditions.append("ae.role = ?")
            params.append(role)
        if namespace is not None:
            conditions.append("ae.entity_iri LIKE ? || ':%'")
            params.append(namespace)

        where = " AND ".join(conditions)
        return [
            r[0]
            for r in ont.conn.execute(
                f"SELECT DISTINCT ae.entity_iri FROM axiom_entities ae{joins} WHERE {where}",
                params,
            )
        ]

    # Text search path
    matches = _find_text_matches(ont, query, _LOCAL_NAME, "iri")
    matches.update(_find_text_matches(ont, query, None, "annotation"))

    if within_selection is not None and matches:
        sel = selections.get_info(ont, within_selection)
        if sel.kind == SelectionKind.ENTITIES:
            allowed = {
                r[0]
                for r in ont.conn.execute(
                    "SELECT item FROM selection_items WHERE selection_name = ?", (within_selection,)
                )
            }
        else:
            allowed = {
                r[0]
                for r in ont.conn.execute(
                    "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
                    "JOIN axioms a ON a.id = ae.axiom_id "
                    "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ?",
                    (within_selection,),
                )
            }
        matches = {k: v for k, v in matches.items() if k in allowed}

    if role is not None and matches:
        role_iris = _batch_check_roles(ont, list(matches.keys()), role)
        matches = {k: v for k, v in matches.items() if k in role_iris}
    if namespace is not None:
        prefix = f"{namespace}:"
        matches = {k: v for k, v in matches.items() if k.startswith(prefix)}

    return list(matches.keys())


def summary(ont: Ontology, *, within_selection: str | None = None) -> tuple[int, Counter[str]]:
    if within_selection is None:
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

    sel = selections.get_info(ont, within_selection)
    if sel.kind == SelectionKind.ENTITIES:
        total = ont.conn.execute(
            "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
            "JOIN selection_items si ON si.item = ae.entity_iri AND si.selection_name = ?",
            (within_selection,),
        ).fetchone()[0]
        role_counts = Counter(
            {
                r[0]: r[1]
                for r in ont.conn.execute(
                    "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
                    "JOIN selection_items si ON si.item = ae.entity_iri AND si.selection_name = ? "
                    "WHERE ae.role IS NOT NULL GROUP BY ae.role",
                    (within_selection,),
                )
            }
        )
    else:  # axioms
        total = ont.conn.execute(
            "SELECT COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
            "JOIN axioms a ON a.id = ae.axiom_id "
            "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ?",
            (within_selection,),
        ).fetchone()[0]
        role_counts = Counter(
            {
                r[0]: r[1]
                for r in ont.conn.execute(
                    "SELECT ae.role, COUNT(DISTINCT ae.entity_iri) FROM axiom_entities ae "
                    "JOIN axioms a ON a.id = ae.axiom_id "
                    "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
                    "WHERE ae.role IS NOT NULL GROUP BY ae.role",
                    (within_selection,),
                )
            }
        )
    return total, role_counts


# -- Private helpers --


def _list_entities(
    ont: Ontology,
    role: str | None,
    namespace: str | None,
    within_selection: str | None,
    limit: int,
    offset: int,
) -> EntitySearchPage:
    conditions = ["ae.role IS NOT NULL"]
    params: list[str | int] = []
    joins = ""

    if within_selection is not None:
        sel = selections.get_info(ont, within_selection)
        if sel.kind == SelectionKind.ENTITIES:
            joins = " JOIN selection_items si_w ON si_w.item = ae.entity_iri AND si_w.selection_name = ?"
            params.append(within_selection)
        else:
            joins = (
                " JOIN axioms a_w ON a_w.id = ae.axiom_id"
                " JOIN selection_items si_w ON si_w.item = a_w.hash AND si_w.selection_name = ?"
            )
            params.append(within_selection)

    if role is not None:
        conditions.append("ae.role = ?")
        params.append(role)
    if namespace is not None:
        conditions.append("ae.entity_iri LIKE ? || ':%'")
        params.append(namespace)

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
    within_selection: str | None,
    limit: int,
    offset: int,
) -> EntitySearchPage:
    matches = _find_text_matches(ont, query, _LOCAL_NAME, "iri")
    matches.update(_find_text_matches(ont, query, None, "annotation"))

    if within_selection is not None and matches:
        sel = selections.get_info(ont, within_selection)
        if sel.kind == SelectionKind.ENTITIES:
            allowed = {
                r[0]
                for r in ont.conn.execute(
                    "SELECT item FROM selection_items WHERE selection_name = ?", (within_selection,)
                )
            }
        else:
            allowed = {
                r[0]
                for r in ont.conn.execute(
                    "SELECT DISTINCT ae.entity_iri FROM axiom_entities ae "
                    "JOIN axioms a ON a.id = ae.axiom_id "
                    "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ?",
                    (within_selection,),
                )
            }
        matches = {k: v for k, v in matches.items() if k in allowed}

    if role is not None and matches:
        role_iris = _batch_check_roles(ont, list(matches.keys()), role)
        matches = {k: v for k, v in matches.items() if k in role_iris}
    if namespace is not None:
        prefix = f"{namespace}:"
        matches = {k: v for k, v in matches.items() if k.startswith(prefix)}

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


def _find_text_matches(
    ont: Ontology,
    query: str,
    property_filter: str | None,
    source_label: str,
) -> dict[str, tuple[str, str]]:
    """Returns {iri: (source_label, quality)}."""
    if property_filter is not None:
        prop_cond = "property = ?"
        prop_param = property_filter
    else:
        prop_cond = "property != ?"
        prop_param = _LOCAL_NAME

    matches: dict[str, tuple[str, str]] = {}
    query_lower = query.lower()

    for (iri_str,) in ont.conn.execute(
        f"SELECT DISTINCT entity_iri FROM entity_text WHERE {prop_cond} AND LOWER(text) = ?",
        (prop_param, query_lower),
    ):
        if iri_str not in matches:
            matches[iri_str] = (source_label, "exact")

    for (iri_str,) in ont.conn.execute(
        f"SELECT DISTINCT entity_iri FROM entity_text WHERE {prop_cond} AND INSTR(LOWER(text), ?) > 0",
        (prop_param, query_lower),
    ):
        if iri_str not in matches:
            matches[iri_str] = (source_label, "substring")

    return matches
