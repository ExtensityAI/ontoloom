from collections.abc import Iterable, Sequence

from ontoloom.axioms.hashing import AxiomHash
from ontoloom.connection import Session
from ontoloom.entities.find_duplicate_entities import FindDuplicateEntities
from ontoloom.entities.text import LOCAL_NAME_PROPERTY
from ontoloom.entities.types import (
    AnnotationRow,
    DuplicateResult,
    EntityInfo,
    EntitySummary,
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
    EntityTextMatches,
    HasAnyProperty,
    HasRole,
    InAxiomSelection,
    InNamespaces,
    MentionsAll,
    WithRoles,
)
from ontoloom.query.count_axioms_by_type import CountAxiomsByType
from ontoloom.query.count_entities import CountEntities
from ontoloom.query.count_entities_by_role import CountEntitiesByRole
from ontoloom.query.dispatch import execute, resolve_within
from ontoloom.query.find_axioms import FindAxioms
from ontoloom.query.find_entities import FindEntities
from ontoloom.selections.types import SelectionName
from ontoloom.utils import dquoted


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


def get_entity(s: Session, iri: IRI, *, within: SelectionName | None = None) -> EntityInfo:
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
    axiom_counts = execute(s, CountAxiomsByType(constraints=axiom_count_constraints))

    if not roles and not annotations and not axiom_counts:
        near = find_entities(s, query=iri.local_name)[:_NEAR_MATCH_LIMIT]
        raise EntityNotFoundError(iri_str, [str(m) for m in near])
    return EntityInfo(
        roles=frozenset(roles), annotations=tuple(annotations), axiom_counts=axiom_counts
    )


def axiom_hashes_for_entity(
    s: Session, iri: IRI, *, within: SelectionName | None = None
) -> list[AxiomHash]:
    """Return all axiom hashes for an entity."""
    constraints: tuple[AxiomConstraint, ...] = (
        MentionsAll(iris=(iri,)),
        *((InAxiomSelection(name=within),) if within is not None else ()),
    )
    return execute(s, FindAxioms(constraints=constraints))


def find_entities(
    s: Session,
    *,
    query: str | None = None,
    role: EntityType | None = None,
    namespace: PrefixName | None = None,
    within: SelectionName | None = None,
    declared: bool | None = None,
    properties: Sequence[IRI] = (),
    exclude_deprecated: bool = True,
) -> list[IRI]:
    """Return all matching entity IRIs, ranked when `query` is given else IRI-ordered.

    query: substring match on IRI local names and annotation values; ranks
    local-name-exact, annotation-exact, local-name-substring, annotation-substring.
    within: scope to a named selection. Entity selection restricts to those
    specific entities; axiom selection restricts to entities mentioned in those axioms.
    declared: True = only declared entities, False = only undeclared, None = all.
    properties: restrict text search to these annotation properties; when query is None,
    find entities that have any annotation with these properties.
    exclude_deprecated: exclude entities with owl:deprecated "true" annotation.
    """
    constraints = _build_entity_constraints(
        s,
        query=query,
        role=role,
        namespace=namespace,
        within=within,
        declared=declared,
        properties=properties,
        exclude_deprecated=exclude_deprecated,
    )
    return execute(s, FindEntities(constraints=constraints))


def summarize_entities(s: Session, *, within: SelectionName | None = None) -> EntitySummary:
    constraints: tuple[EntityConstraint, ...] = (
        HasRole(),
        *((resolve_within(s, within),) if within is not None else ()),
    )
    total = execute(s, CountEntities(constraints=constraints))
    by_role = execute(s, CountEntitiesByRole(constraints=constraints))
    return EntitySummary(total=total, by_role=by_role)


def find_duplicate_entities(
    s: Session,
    annotation_property: IRI,
    *,
    within: SelectionName | None = None,
) -> DuplicateResult:
    """Find annotation values shared by multiple entities."""
    return execute(s, FindDuplicateEntities(annotation_property=annotation_property, within=within))


# -- Private helpers --


def _build_entity_constraints(
    s: Session,
    *,
    query: str | None,
    role: EntityType | None,
    namespace: PrefixName | None,
    within: SelectionName | None,
    declared: bool | None,
    properties: Sequence[IRI],
    exclude_deprecated: bool,
) -> tuple[EntityConstraint, ...]:
    """Build the constraint tuple for entity search.

    With a text query, `EntityTextMatches` anchors the set (and scopes annotation
    search to `properties`). Without one, `HasRole()` anchors the full-entity feed
    and `properties` become a `HasAnyProperty` existence filter.
    """
    constraints: list[EntityConstraint] = []

    if query is not None:
        constraints.append(EntityTextMatches(query=query, properties=tuple(properties)))
    else:
        constraints.append(HasRole())

        if properties:
            constraints.append(HasAnyProperty(properties=tuple(properties)))

    if role is not None:
        constraints.append(WithRoles(roles=(role,)))
    if namespace is not None:
        constraints.append(InNamespaces(namespaces=(namespace,)))
    if within is not None:
        constraints.append(resolve_within(s, within))
    if declared is not None:
        constraints.append(Declared(state=declared))
    if exclude_deprecated:
        constraints.append(Deprecated(state=False))

    return tuple(constraints)


def count_undeclared_entities(
    s: Session,
    within: SelectionName | None = None,
    *,
    exclude_deprecated: bool = True,
) -> int:
    """Count distinct entities that lack a Declaration axiom.

    `exclude_deprecated=True` matches `find_entities(declared=False)` defaults.
    Set False to count every undeclared entity including deprecated ones.
    """
    constraints: tuple[EntityConstraint, ...] = (
        HasRole(),
        Declared(state=False),
        *((Deprecated(state=False),) if exclude_deprecated else ()),
        *((resolve_within(s, within),) if within is not None else ()),
    )
    return execute(s, CountEntities(constraints=constraints))
