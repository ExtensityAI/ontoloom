from collections.abc import Iterable, Sequence

from ontoloom.axioms.hashing import AxiomHash
from ontoloom.connection import Session
from ontoloom.entities.find_duplicate_entities import FindDuplicateEntities
from ontoloom.entities.projections import (
    batch_fetch_entity_display,
    find_text_matches,
)
from ontoloom.entities.text import LOCAL_NAME_PROPERTY
from ontoloom.entities.types import (
    AnnotationRow,
    DuplicateResult,
    EntityDisplay,
    EntityInfo,
    EntityMatch,
    EntitySearchPage,
    EntitySummary,
    MatchQuality,
    MatchSource,
    TextMatch,
)
from ontoloom.errors import OntoloomError
from ontoloom.owl.iri import IRI, RDFS_LABEL
from ontoloom.owl.markers import EntityType
from ontoloom.prefixes.types import PrefixName
from ontoloom.query.constraints import (
    AxiomConstraint,
    Declared,
    Deprecated,
    EntityConstraint,
    HasAnyProperty,
    HasRole,
    InAxiomSelection,
    InEntitySelection,
    InIRIs,
    InNamespaces,
    MentionsAll,
    WithRoles,
)
from ontoloom.query.count_axioms_by_type import CountAxiomsByType
from ontoloom.query.count_entities import CountEntities
from ontoloom.query.count_entities_by_role import CountEntitiesByRole
from ontoloom.query.dispatch import run
from ontoloom.query.list_axiom_hashes import ListAxiomHashes
from ontoloom.query.list_entities import ListEntities
from ontoloom.selections.types import (
    AxiomSelectionName,
    EntitySelectionName,
)
from ontoloom.utils import dquoted

type SelectionRef = AxiomSelectionName | EntitySelectionName


def _in_selection_entity(within: SelectionRef) -> EntityConstraint:
    if isinstance(within, AxiomSelectionName):
        return InAxiomSelection(name=within)
    return InEntitySelection(name=within)


class EntityNotFoundError(OntoloomError):
    """No entity with the given IRI exists in the ontology.

    `near_matches` are IRIs of entities with similar local names, for
    surfacing "did you mean…?" hints without a follow-up query.
    """

    def __init__(self, iri: str, near_matches: Sequence[str] = ()):
        self.iri = iri
        self.near_matches = near_matches
        super().__init__(f"Entity {dquoted(iri)} not found.")


_NEAR_MATCH_LIMIT = 3


_LABEL_BATCH_SIZE = 500

_EMPTY_DISPLAY = EntityDisplay(roles=frozenset(), annotations=())


def lookup_entity_labels(s: Session, iris: Iterable[str]) -> dict[str, str | None]:
    """Return {iri: rdfs:label | None} for each IRI in the input."""
    iri_list = list(iris)
    result: dict[str, str | None] = dict.fromkeys(iri_list)
    for i in range(0, len(iri_list), _LABEL_BATCH_SIZE):
        batch = iri_list[i : i + _LABEL_BATCH_SIZE]
        ph = ",".join("?" for _ in batch)
        result.update(
            s.conn.execute(
                f"SELECT entity_iri, text FROM entity_text "
                f"WHERE entity_iri IN ({ph}) AND property = ?",
                (*batch, RDFS_LABEL),
            ).fetchall()
        )
    return result


def get_entity(s: Session, iri: IRI, *, within: AxiomSelectionName | None = None) -> EntityInfo:
    """Return entity details. Raises EntityNotFoundError (with near matches) on miss."""
    iri_str = str(iri)

    roles = {
        EntityType(r[0])
        for r in s.conn.execute(
            "SELECT DISTINCT role FROM axiom_entities WHERE entity_iri = ? AND role IS NOT NULL",
            (iri_str,),
        )
    }

    annotations = [
        AnnotationRow(property=IRI(r[0]), value=r[1])
        for r in s.conn.execute(
            "SELECT DISTINCT property, text FROM entity_text "
            "WHERE entity_iri = ? AND property != ? "
            "ORDER BY property, text",
            (iri_str, LOCAL_NAME_PROPERTY),
        )
    ]

    axiom_count_constraints: tuple[AxiomConstraint, ...] = (
        MentionsAll(iris=(iri,)),
        *((InAxiomSelection(name=within),) if within is not None else ()),
    )
    axiom_counts = run(s, CountAxiomsByType(constraints=axiom_count_constraints))

    if not roles and not annotations and not axiom_counts:
        near = search_entities(s, query=iri.local_name, limit=_NEAR_MATCH_LIMIT)
        raise EntityNotFoundError(iri_str, [str(m.iri) for m in near.matches])
    return EntityInfo(
        roles=frozenset(roles), annotations=tuple(annotations), axiom_counts=axiom_counts
    )


def axiom_hashes_for_entity(
    s: Session, iri: IRI, *, within: AxiomSelectionName | None = None
) -> list[AxiomHash]:
    """Return all axiom hashes for an entity."""
    constraints: tuple[AxiomConstraint, ...] = (
        MentionsAll(iris=(iri,)),
        *((InAxiomSelection(name=within),) if within is not None else ()),
    )
    return run(s, ListAxiomHashes(constraints=constraints))


def search_entities(
    s: Session,
    *,
    query: str | None = None,
    role: EntityType | None = None,
    namespace: PrefixName | None = None,
    within: SelectionRef | None = None,
    declared: bool | None = None,
    properties: Sequence[IRI] = (),
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
    within: SelectionRef | None = None,
    declared: bool | None = None,
    properties: Sequence[IRI] = (),
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
    matches = find_text_matches(s, query, LOCAL_NAME_PROPERTY, MatchSource.IRI)
    matches.update(find_text_matches(s, query, None, MatchSource.ANNOTATION, properties=properties))
    matches = _apply_text_filters(s, matches, role, namespace, within, declared, exclude_deprecated)
    return [IRI(k) for k in matches]


def entity_summary(s: Session, *, within: SelectionRef | None = None) -> EntitySummary:
    constraints: tuple[EntityConstraint, ...] = (
        HasRole(),
        *((_in_selection_entity(within),) if within is not None else ()),
    )
    total = run(s, CountEntities(constraints=constraints))
    by_role = run(s, CountEntitiesByRole(constraints=constraints))
    return EntitySummary(total=total, by_role=by_role)


def find_duplicate_entities(
    s: Session,
    annotation_property: IRI,
    *,
    within: EntitySelectionName | None = None,
) -> DuplicateResult:
    """Find annotation values shared by multiple entities."""
    return run(s, FindDuplicateEntities(annotation_property=annotation_property, within=within))


# -- Private helpers --


def _build_entity_constraints(
    *,
    role: EntityType | None,
    namespace: PrefixName | None,
    within: SelectionRef | None,
    declared: bool | None,
    properties: Sequence[IRI],
    exclude_deprecated: bool,
) -> tuple[EntityConstraint, ...]:
    """Build the constraint tuple for the non-text entity search path."""
    constraints: list[EntityConstraint] = [HasRole()]

    if role is not None:
        constraints.append(WithRoles(roles=(role,)))
    if namespace is not None:
        constraints.append(InNamespaces(namespaces=(namespace,)))
    if within is not None:
        constraints.append(_in_selection_entity(within))
    if declared is not None:
        constraints.append(Declared(state=declared))
    if properties:
        constraints.append(HasAnyProperty(properties=tuple(properties)))
    if exclude_deprecated:
        constraints.append(Deprecated(state=False))

    return tuple(constraints)


def _apply_text_filters(
    s: Session,
    matches: dict[str, TextMatch],
    role: EntityType | None,
    namespace: PrefixName | None,
    within: SelectionRef | None,
    declared: bool | None,
    exclude_deprecated: bool,
) -> dict[str, TextMatch]:
    """Apply post-text-search filters to candidate matches via a single ListEntities call."""
    if not matches:
        return matches

    constraints: list[EntityConstraint] = [InIRIs(iris=tuple(IRI(k) for k in matches))]

    if within is not None:
        constraints.append(_in_selection_entity(within))
    if role is not None:
        constraints.append(WithRoles(roles=(role,)))
    if namespace is not None:
        constraints.append(InNamespaces(namespaces=(namespace,)))
    if declared is not None:
        constraints.append(Declared(state=declared))
    if exclude_deprecated:
        constraints.append(Deprecated(state=False))

    surviving = set(run(s, ListEntities(constraints=tuple(constraints))))

    return {k: v for k, v in matches.items() if k in surviving}


def _list_entities(
    s: Session,
    role: EntityType | None,
    namespace: PrefixName | None,
    within: SelectionRef | None,
    declared: bool | None,
    properties: Sequence[IRI],
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

    display = batch_fetch_entity_display(s, [str(i) for i in page_iris])

    return EntitySearchPage(
        matches=tuple(
            EntityMatch(
                iri=iri,
                roles=display.get(str(iri), _EMPTY_DISPLAY).roles,
                annotations=display.get(str(iri), _EMPTY_DISPLAY).annotations,
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
    within: SelectionRef | None,
    declared: bool | None,
    properties: Sequence[IRI],
    exclude_deprecated: bool,
    limit: int,
    offset: int,
) -> EntitySearchPage:
    matches = find_text_matches(s, query, LOCAL_NAME_PROPERTY, MatchSource.IRI)
    matches.update(find_text_matches(s, query, None, MatchSource.ANNOTATION, properties=properties))
    matches = _apply_text_filters(s, matches, role, namespace, within, declared, exclude_deprecated)

    quality_order = {MatchQuality.EXACT: 0, MatchQuality.SUBSTRING: 1}
    source_order = {MatchSource.IRI: 0, MatchSource.ANNOTATION: 1}
    sorted_iris = sorted(
        matches.keys(),
        key=lambda k: (
            quality_order.get(matches[k].quality, 9),
            source_order.get(matches[k].source, 9),
            k,
        ),
    )

    total = len(sorted_iris)
    page_iris = sorted_iris[offset : offset + limit]
    if not page_iris:
        return EntitySearchPage(matches=(), total=total, offset=offset)

    display = batch_fetch_entity_display(s, page_iris)
    return EntitySearchPage(
        matches=tuple(
            EntityMatch(
                iri=IRI(iri_str),
                roles=display.get(iri_str, _EMPTY_DISPLAY).roles,
                annotations=display.get(iri_str, _EMPTY_DISPLAY).annotations,
                match_source=matches[iri_str].source,
                match_quality=matches[iri_str].quality,
            )
            for iri_str in page_iris
        ),
        total=total,
        offset=offset,
    )


def undeclared_entity_count(
    s: Session,
    within: SelectionRef | None = None,
    *,
    exclude_deprecated: bool = True,
) -> int:
    """Count distinct entities that lack a Declaration axiom.

    `exclude_deprecated=True` matches `search_entities(declared=False)` defaults.
    Set False to count every undeclared entity including deprecated ones.
    """
    constraints: tuple[EntityConstraint, ...] = (
        HasRole(),
        Declared(state=False),
        *((Deprecated(state=False),) if exclude_deprecated else ()),
        *((_in_selection_entity(within),) if within is not None else ()),
    )
    return run(s, CountEntities(constraints=constraints))
