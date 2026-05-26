"""Entity and axiom normalization — pure outputs, no DB access."""

from collections.abc import Callable, Sequence

from ontoloom.query.constraints import (
    _MENTIONS_ALL_CAP,
    AlwaysFalse,
    AxiomConstraint,
    Declared,
    Deprecated,
    EntityConstraint,
    HasAnyAnnotation,
    HasAnyProperty,
    HasRole,
    InAxiomSelection,
    InEntitySelection,
    InIRIs,
    InNamespaces,
    InPositions,
    MentionedIn,
    MentionsAll,
    MentionsAllOverflowError,
    MentionsAny,
    WithRoles,
    WithTypes,
)
from ontoloom.utils import dedupe


class _EmptyIntersectionError(Exception):
    """Raised by _intersect when the intersection of collection-field values is empty.

    Module-private control-flow signal; caught inside the same `normalize_*` call
    and converted to `(AlwaysFalse(),)`. Never escapes this module — kept as bare
    `Exception` (not `OntoloomError`-rooted) to make that explicit.
    """


def normalize_entity(cs: Sequence[EntityConstraint]) -> tuple[EntityConstraint, ...]:  # noqa: C901
    """Merge and deduplicate entity constraints according to canonical rules.

    Raises:
        ValueError: if more than one selection-scope constraint is present.
    """
    if not cs:
        return ()

    in_iris: list[InIRIs] = []
    with_roles: list[WithRoles] = []
    has_role: list[HasRole] = []
    in_namespaces: list[InNamespaces] = []
    declared: list[Declared] = []
    deprecated: list[Deprecated] = []
    has_any_property: list[HasAnyProperty] = []
    mentioned_in: list[MentionedIn] = []
    in_positions: list[InPositions] = []
    in_selection: list[InAxiomSelection | InEntitySelection] = []

    for c in cs:
        match c:
            case AlwaysFalse():
                return (AlwaysFalse(),)
            case InIRIs():
                in_iris.append(c)
            case WithRoles():
                with_roles.append(c)
            case HasRole():
                has_role.append(c)
            case InNamespaces():
                in_namespaces.append(c)
            case Declared():
                declared.append(c)
            case Deprecated():
                deprecated.append(c)
            case HasAnyProperty():
                has_any_property.append(c)
            case MentionedIn():
                mentioned_in.append(c)
            case InPositions():
                in_positions.append(c)
            case InAxiomSelection() | InEntitySelection():
                in_selection.append(c)
            case _:
                msg = f"unknown entity constraint variant: {type(c).__name__}"
                raise ValueError(msg)

    if len(in_selection) > 1:
        msg = "a query may have at most one selection scope"
        raise ValueError(msg)

    result: list[EntityConstraint] = []

    if in_selection:
        result.append(in_selection[0])

    try:
        iris_merged = _intersect(in_iris, "iris", lambda v: InIRIs(iris=tuple(v)))
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
    result.extend(dedupe(has_any_property))
    result.extend(dedupe(mentioned_in))

    # Declared: same state → dedupe; different states → AlwaysFalse.
    if declared:
        states = {d.state for d in declared}

        if len(states) > 1:
            return (AlwaysFalse(),)

        result.append(Declared(state=next(iter(states))))

    # Deprecated: same state → dedupe; different states → AlwaysFalse.
    if deprecated:
        states = {d.state for d in deprecated}

        if len(states) > 1:
            return (AlwaysFalse(),)

        result.append(Deprecated(state=next(iter(states))))

    # Nullary variants: dedupe to one.
    if has_role:
        result.append(HasRole())

    return tuple(sorted(result, key=repr))


def normalize_axiom(cs: Sequence[AxiomConstraint]) -> tuple[AxiomConstraint, ...]:  # noqa: C901
    """Merge and deduplicate axiom constraints according to canonical rules.

    Raises:
        ValueError: if more than one selection-scope constraint is present.
    """
    if not cs:
        return ()

    with_types: list[WithTypes] = []
    mentions_all: list[MentionsAll] = []
    mentions_any: list[MentionsAny] = []
    has_any_annotation: list[HasAnyAnnotation] = []
    in_selection: list[InAxiomSelection | InEntitySelection] = []

    for c in cs:
        match c:
            case AlwaysFalse():
                return (AlwaysFalse(),)
            case WithTypes():
                with_types.append(c)
            case MentionsAll():
                mentions_all.append(c)
            case MentionsAny():
                mentions_any.append(c)
            case HasAnyAnnotation():
                has_any_annotation.append(c)
            case InAxiomSelection() | InEntitySelection():
                in_selection.append(c)
            case _:
                msg = f"unknown axiom constraint variant: {type(c).__name__}"
                raise ValueError(msg)

    if len(in_selection) > 1:
        msg = "a query may have at most one selection scope"
        raise ValueError(msg)

    result: list[AxiomConstraint] = []

    if in_selection:
        result.append(in_selection[0])

    try:
        types_merged = _intersect(with_types, "tags", lambda v: WithTypes(tags=tuple(v)))
        if types_merged is not None:
            result.append(types_merged)
    except _EmptyIntersectionError:
        return (AlwaysFalse(),)

    if mentions_all:
        union = sorted({iri for m in mentions_all for iri in m.iris})

        if len(union) > _MENTIONS_ALL_CAP:
            raise MentionsAllOverflowError(count=len(union), cap=_MENTIONS_ALL_CAP)

        result.append(MentionsAll(iris=tuple(union)))

    # Non-mergeable: dedupe exact-value-equal duplicates only.
    result.extend(dedupe(mentions_any))
    result.extend(dedupe(has_any_annotation))

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
