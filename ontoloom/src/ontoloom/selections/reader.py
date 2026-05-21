"""High-level paginated reads of a selection's items, polymorphic over kind.

Sits above `selections.persistence` and the `query/` layer: dispatches by the
caller's kind-typed ref to the matching `Read*Selection` query, which fetches
the selection's metadata and enforces the prefix-vs-stored-kind match.
"""

from typing import Annotated, overload

from pydantic import Field

from ontoloom.connection import Session
from ontoloom.query.dispatch import run
from ontoloom.query.read_axiom_selection import ReadAxiomSelection
from ontoloom.query.read_entity_selection import ReadEntitySelection
from ontoloom.selections.types import (
    AxiomSelectionName,
    AxiomSelectionPage,
    EntitySelectionName,
    EntitySelectionPage,
    SelectionRef,
    ShowFilter,
)


@overload
def read_selection(
    s: Session,
    name: AxiomSelectionName,
    *,
    limit: Annotated[int, Field(ge=1)] = 20,
    offset: int = 0,
    show: ShowFilter = ShowFilter.ALL,
) -> AxiomSelectionPage: ...


@overload
def read_selection(
    s: Session,
    name: EntitySelectionName,
    *,
    limit: Annotated[int, Field(ge=1)] = 20,
    offset: int = 0,
    show: ShowFilter = ShowFilter.ALL,
) -> EntitySelectionPage: ...


def read_selection(
    s: Session,
    name: SelectionRef,
    *,
    limit: Annotated[int, Field(ge=1)] = 20,
    offset: int = 0,
    show: ShowFilter = ShowFilter.ALL,
) -> AxiomSelectionPage | EntitySelectionPage:
    if isinstance(name, AxiomSelectionName):
        return run(s, ReadAxiomSelection(selection=name, limit=limit, offset=offset, show=show))
    return run(s, ReadEntitySelection(selection=name, limit=limit, offset=offset, show=show))
