"""Entity and axiom normalization — pure outputs, no DB access."""

from collections.abc import Callable, Sequence

from ontoloom.query._constraints import (
    AlwaysFalse,
    AxiomConstraint,
    Declared,
    EntityConstraint,
    HasEntityRole,
    InNamespaces,
    InPositions,
    InSelection,
    MentionedInAxioms,
    MentionsAll,
    MentionsAny,
    NotDeprecated,
    OfTypes,
    WithAnyProperty,
    WithIRIs,
    WithRoles,
)


class _EmptyIntersectionError(Exception):
    """Raised by _intersect when the intersection of collection-field values is empty."""


def normalize_entity(cs: Sequence[EntityConstraint]) -> tuple[EntityConstraint, ...]:  # noqa: C901
    """Merge and deduplicate entity constraints according to canonical rules.

    Raises:
        ValueError: if more than one InSelection constraint is present.
    """
    if not cs:
        return ()

    with_iris: list[WithIRIs] = []
    with_roles: list[WithRoles] = []
    has_entity_role: list[HasEntityRole] = []
    in_namespaces: list[InNamespaces] = []
    declared: list[Declared] = []
    not_deprecated: list[NotDeprecated] = []
    with_any_property: list[WithAnyProperty] = []
    mentioned_in_axioms: list[MentionedInAxioms] = []
    in_positions: list[InPositions] = []
    in_selection: list[InSelection] = []

    for c in cs:
        if isinstance(c, AlwaysFalse):
            return (AlwaysFalse(),)

        if isinstance(c, WithIRIs):
            with_iris.append(c)
        elif isinstance(c, WithRoles):
            with_roles.append(c)
        elif isinstance(c, HasEntityRole):
            has_entity_role.append(c)
        elif isinstance(c, InNamespaces):
            in_namespaces.append(c)
        elif isinstance(c, Declared):
            declared.append(c)
        elif isinstance(c, NotDeprecated):
            not_deprecated.append(c)
        elif isinstance(c, WithAnyProperty):
            with_any_property.append(c)
        elif isinstance(c, MentionedInAxioms):
            mentioned_in_axioms.append(c)
        elif isinstance(c, InPositions):
            in_positions.append(c)
        elif isinstance(c, InSelection):
            in_selection.append(c)

    if len(in_selection) > 1:
        msg = "a query may have at most one selection scope"
        raise ValueError(msg)

    result: list[EntityConstraint] = []

    if in_selection:
        result.append(in_selection[0])

    try:
        iris_merged = _intersect(with_iris, "iris", lambda v: WithIRIs(iris=tuple(v)))
        if iris_merged is not None:
            result.append(iris_merged)

        roles_merged = _intersect(with_roles, "roles", lambda v: WithRoles(roles=tuple(v)))
        if roles_merged is not None:
            result.append(roles_merged)

        ns_merged = _intersect(
            in_namespaces, "namespaces", lambda v: InNamespaces(namespaces=tuple(v))
        )
        if ns_merged is not None:
            result.append(ns_merged)

        pos_merged = _intersect(
            in_positions, "positions", lambda v: InPositions(positions=tuple(v))
        )
        if pos_merged is not None:
            result.append(pos_merged)
    except _EmptyIntersectionError:
        return (AlwaysFalse(),)

    # Non-mergeable: dedupe exact-value-equal duplicates only.
    result.extend(_dedupe(with_any_property))
    result.extend(_dedupe(mentioned_in_axioms))

    # Declared: same state → dedupe; different states → AlwaysFalse.
    if declared:
        states = {d.state for d in declared}

        if len(states) > 1:
            return (AlwaysFalse(),)

        result.append(Declared(state=next(iter(states))))

    # Nullary variants: dedupe to one.
    if has_entity_role:
        result.append(HasEntityRole())

    if not_deprecated:
        result.append(NotDeprecated())

    return tuple(sorted(result, key=repr))


def normalize_axiom(cs: Sequence[AxiomConstraint]) -> tuple[AxiomConstraint, ...]:  # noqa: C901
    """Merge and deduplicate axiom constraints according to canonical rules.

    Raises:
        ValueError: if more than one InSelection constraint is present.
    """
    if not cs:
        return ()

    of_types: list[OfTypes] = []
    mentions_all: list[MentionsAll] = []
    mentions_any: list[MentionsAny] = []
    in_selection: list[InSelection] = []

    for c in cs:
        if isinstance(c, AlwaysFalse):
            return (AlwaysFalse(),)

        if isinstance(c, OfTypes):
            of_types.append(c)
        elif isinstance(c, MentionsAll):
            mentions_all.append(c)
        elif isinstance(c, MentionsAny):
            mentions_any.append(c)
        elif isinstance(c, InSelection):
            in_selection.append(c)

    if len(in_selection) > 1:
        msg = "a query may have at most one selection scope"
        raise ValueError(msg)

    result: list[AxiomConstraint] = []

    if in_selection:
        result.append(in_selection[0])

    try:
        types_merged = _intersect(of_types, "tags", lambda v: OfTypes(tags=tuple(v)))
        if types_merged is not None:
            result.append(types_merged)
    except _EmptyIntersectionError:
        return (AlwaysFalse(),)

    # MentionsAll: union IRI collections. Pydantic raises ValidationError if the
    # union exceeds the 8-IRI cap; that is a caller bug.
    if mentions_all:
        union = sorted({iri for m in mentions_all for iri in m.iris})
        result.append(MentionsAll(iris=tuple(union)))

    # Non-mergeable: dedupe exact-value-equal duplicates only.
    result.extend(_dedupe(mentions_any))

    return tuple(sorted(result, key=repr))


def _intersect[C, V: str](
    instances: list[C],
    field: str,
    build: Callable[[list[V]], C],
) -> C | None:
    """Intersect the named collection field across all instances.

    Returns None if there are no instances. Returns the sole instance if there is
    exactly one. Otherwise builds a merged constraint from the intersection.

    Raises:
        _EmptyIntersection: if the intersection of values across instances is empty.
    """
    if not instances:
        return None

    if len(instances) == 1:
        return instances[0]

    intersection: set[V] = set(getattr(instances[0], field))

    for inst in instances[1:]:
        intersection &= set(getattr(inst, field))

    if not intersection:
        raise _EmptyIntersectionError

    return build(sorted(intersection))


def _dedupe[C](instances: list[C]) -> list[C]:
    """Return instances with exact-value-equal duplicates removed, preserving first-seen order."""
    seen: list[C] = []

    for inst in instances:
        if inst not in seen:
            seen.append(inst)

    return seen
