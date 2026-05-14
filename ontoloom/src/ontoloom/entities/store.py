from ontoloom.connection import Session
from ontoloom.entities.types import (
    AnnotationRow,
    DuplicateResult,
    EntityInfo,
    EntityMatch,
    EntitySearchPage,
    EntitySummary,
    MatchQuality,
    MatchSource,
)
from ontoloom.errors import OntoloomError
from ontoloom.hashing import AxiomHash
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.prefixes.types import PrefixName
from ontoloom.query._constraints import (
    AxiomConstraint,
    Declared,
    EntityConstraint,
    HasEntityRole,
    InNamespaces,
    InSelection,
    MentionsAll,
    NotDeprecated,
    WithAnyProperty,
    WithIRIs,
    WithRoles,
)
from ontoloom.query._dispatch import run
from ontoloom.query._selection_ref import ResolvedSelection
from ontoloom.query.count_axioms_by_type import CountAxiomsByType
from ontoloom.query.count_entities import CountEntities
from ontoloom.query.count_entities_by_role import CountEntitiesByRole
from ontoloom.query.find_duplicate_entities import FindDuplicateEntities
from ontoloom.query.list_axiom_hashes import ListAxiomHashes
from ontoloom.query.list_entities import ListEntities
from ontoloom.selections.types import SelectionKind
from ontoloom.text_index import (
    LOCAL_NAME_PROPERTY,
)
from ontoloom.utils import dquoted


class EntityNotFoundError(OntoloomError):
    """No entity with the given IRI exists in the ontology.

    `near_matches` are IRIs of entities with similar local names -> populated by
    `entities.get` so callers can show "did you mean…?" without re-querying.
    """

    def __init__(self, iri: str, near_matches: list[str] | None = None):
        self.iri = iri
        self.near_matches = near_matches or []
        super().__init__(f"Entity {dquoted(iri)} not found.")


# A: this file is huge. we need to look at it separately

_TEXT_SCAN_CAP = 1000


_NEAR_MATCH_LIMIT = 3


def get_entity(s: Session, iri: IRI, *, within: ResolvedSelection | None = None) -> EntityInfo:
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

    axiom_count_constraints: tuple[AxiomConstraint, ...] = (
        MentionsAll(iris=(iri,)),
        *(
            (InSelection(ref=within, expected_kind=SelectionKind.AXIOMS),)
            if within is not None
            else ()
        ),
    )
    axiom_counts = run(s, CountAxiomsByType(constraints=axiom_count_constraints))

    if not roles and not annotations and not axiom_counts:
        near = search_entities(s, query=iri.local_name, limit=_NEAR_MATCH_LIMIT)
        raise EntityNotFoundError(iri_str, [str(m.iri) for m in near.matches])
    return EntityInfo(
        roles=frozenset(roles), annotations=tuple(annotations), axiom_counts=axiom_counts
    )


def axiom_hashes_for_entity(
    s: Session, iri: IRI, *, within: ResolvedSelection | None = None
) -> list[AxiomHash]:
    """Return all axiom hashes for an entity."""
    constraints: tuple[AxiomConstraint, ...] = (
        MentionsAll(iris=(iri,)),
        *(
            (InSelection(ref=within, expected_kind=SelectionKind.AXIOMS),)
            if within is not None
            else ()
        ),
    )
    return run(s, ListAxiomHashes(constraints=constraints))


def search_entities(
    s: Session,
    *,
    query: str | None = None,
    role: EntityType | None = None,
    namespace: PrefixName | None = None,
    within: ResolvedSelection | None = None,
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
    within: ResolvedSelection | None = None,
    declared: bool | None = None,
    properties: list[IRI] | None = None,
    exclude_deprecated: bool = True,
) -> list[IRI]:
    """Return all matching entity IRIs (no display data). For select workflows."""
    if query is None:
        constraints = _build_entity_constraints(
            role=role,
            namespace=namespace,
            within=within,
            declared=declared,
            properties=properties,
            exclude_deprecated=exclude_deprecated,
        )
        return run(s, ListEntities(constraints=constraints))

    # Text search path
    matches = _find_text_matches(s, query, LOCAL_NAME_PROPERTY, MatchSource.IRI, properties=None)
    matches.update(
        _find_text_matches(s, query, None, MatchSource.ANNOTATION, properties=properties)
    )
    matches = _apply_text_filters(s, matches, role, namespace, within, declared, exclude_deprecated)
    return [IRI(k) for k in matches]


def entity_summary(s: Session, *, within: ResolvedSelection | None = None) -> EntitySummary:
    constraints: tuple[EntityConstraint, ...] = (
        HasEntityRole(),
        *((InSelection(ref=within),) if within is not None else ()),
    )
    total = run(s, CountEntities(constraints=constraints))
    by_role = run(s, CountEntitiesByRole(constraints=constraints))
    return EntitySummary(total=total, by_role=by_role)


def find_duplicate_entities(
    s: Session,
    annotation_property: IRI,
    *,
    within: ResolvedSelection | None = None,
) -> DuplicateResult:
    """Find annotation values shared by multiple entities."""
    return run(s, FindDuplicateEntities(annotation_property=annotation_property, within=within))


# -- Private helpers --


def _build_entity_constraints(
    *,
    role: EntityType | None,
    namespace: PrefixName | None,
    within: ResolvedSelection | None,
    declared: bool | None,
    properties: list[IRI] | None,
    exclude_deprecated: bool,
) -> tuple[EntityConstraint, ...]:
    """Build the constraint tuple for the non-text entity search path."""
    constraints: list[EntityConstraint] = [HasEntityRole()]

    if role is not None:
        constraints.append(WithRoles(roles=(role,)))
    if namespace is not None:
        constraints.append(InNamespaces(namespaces=(namespace,)))
    if within is not None:
        constraints.append(InSelection(ref=within))
    if declared is not None:
        constraints.append(Declared(state=declared))
    if properties is not None:
        constraints.append(WithAnyProperty(properties=tuple(properties)))
    if exclude_deprecated:
        constraints.append(NotDeprecated())

    return tuple(constraints)


def _apply_text_filters(
    s: Session,
    matches: dict[str, tuple[MatchSource, MatchQuality]],
    role: EntityType | None,
    namespace: PrefixName | None,
    within: ResolvedSelection | None,
    declared: bool | None,
    exclude_deprecated: bool,
) -> dict[str, tuple[MatchSource, MatchQuality]]:
    """Apply post-text-search filters to candidate matches via a single ListEntities call."""
    if not matches:
        return matches

    constraints: list[EntityConstraint] = [WithIRIs(iris=tuple(IRI(k) for k in matches))]

    if within is not None:
        constraints.append(InSelection(ref=within))
    if role is not None:
        constraints.append(WithRoles(roles=(role,)))
    if namespace is not None:
        constraints.append(InNamespaces(namespaces=(namespace,)))
    if declared is not None:
        constraints.append(Declared(state=declared))
    if exclude_deprecated:
        constraints.append(NotDeprecated())

    surviving = set(run(s, ListEntities(constraints=tuple(constraints))))

    return {k: v for k, v in matches.items() if k in surviving}


def _list_entities(
    s: Session,
    role: EntityType | None,
    namespace: PrefixName | None,
    within: ResolvedSelection | None,
    declared: bool | None,
    properties: list[IRI] | None,
    exclude_deprecated: bool,
    limit: int,
    offset: int,
) -> EntitySearchPage:
    constraints = _build_entity_constraints(
        role=role,
        namespace=namespace,
        within=within,
        declared=declared,
        properties=properties,
        exclude_deprecated=exclude_deprecated,
    )
    total = run(s, CountEntities(constraints=constraints))
    page_iris = run(s, ListEntities(constraints=constraints, limit=limit, offset=offset))

    if not page_iris:
        return EntitySearchPage(matches=(), total=total, offset=offset)

    display = _batch_fetch_entity_display(s, [str(i) for i in page_iris])

    return EntitySearchPage(
        matches=tuple(
            EntityMatch(
                iri=iri,
                roles=display.get(str(iri), (frozenset(), ()))[0],
                annotations=display.get(str(iri), (frozenset(), ()))[1],
                match_source=MatchSource.LIST,
                match_quality=MatchQuality.EXACT,
            )
            for iri in page_iris
        ),
        total=total,
        offset=offset,
    )


def _text_search_entities(
    s: Session,
    query: str,
    role: EntityType | None,
    namespace: PrefixName | None,
    within: ResolvedSelection | None,
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
    within: ResolvedSelection | None = None,
    *,
    exclude_deprecated: bool = True,
) -> int:
    """Count distinct entities that lack a Declaration axiom.

    `exclude_deprecated=True` matches `search_entities(declared=False)` defaults.
    Set False to count every undeclared entity including deprecated ones.
    """
    constraints: tuple[EntityConstraint, ...] = (
        HasEntityRole(),
        Declared(state=False),
        *((NotDeprecated(),) if exclude_deprecated else ()),
        *((InSelection(ref=within),) if within is not None else ()),
    )
    return run(s, CountEntities(constraints=constraints))
