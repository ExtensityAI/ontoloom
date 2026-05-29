"""Selection vocabulary: kind-specific identifiers, ops, and read-shape DTOs.

Pure types -> no I/O. Persistence lives in `selections/store.py`; set-expression
evaluation lives in `selections/compose.py`; paginated reads live in
`selections/read_axiom_selection.py` and `selections/read_entity_selection.py`.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import override

from ontoloom.axioms.hashing import AxiomHash
from ontoloom.errors import OntoloomError
from ontoloom.models import TypedStr
from ontoloom.owl.axioms import BaseAxiom
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.utils import dquoted


class SelectionExprError(OntoloomError):
    """Set-expression evaluation precondition violated.

    Covers operand-cardinality issues (no operands, too few for intersect/diff)
    and any boundary-layer kind-routing mismatches when the destination kind
    of the selection doesn't match the kind of the supplied expression.
    """


MAX_SELECTION_NAME_LEN = 64

NAME_FRAGMENT = rf"[a-zA-Z][a-zA-Z0-9._/:-]{{0,{MAX_SELECTION_NAME_LEN - 1}}}"

_NAME_PATTERN = re.compile(rf"^{NAME_FRAGMENT}$")


class ShowFilter(StrEnum):
    """Filter for read_selection item visibility.

    ALL: show all items (present and missing).
    PRESENT: only items still in ontology.
    MISSING: only items no longer found (e.g. deleted axioms). Use to audit selections after modifications.
    """

    ALL = "all"
    PRESENT = "present"
    MISSING = "missing"


class SetOp(StrEnum):
    UNION = "union"
    INTERSECTION = "intersection"
    DIFFERENCE = "difference"


class SelectionKind(StrEnum):
    """One of the two selection kinds (axioms or entities).

    Serves as the wire-form prefix in kind-tagged refs and as the eval-time
    kind result returned by `evaluate_set_expr`.
    """

    AXIOMS = "axioms"
    ENTITIES = "entities"


class SelectionContentHash(TypedStr):
    """Lowercase 16-hex content digest of a selection's sorted items."""

    description = "Selection content hash (16 lowercase hex chars)"
    pattern = r"^[0-9a-f]{16}$"
    examples = ("0123456789abcdef",)

    @override
    @classmethod
    def parse(cls, value: str):
        normalized = value.lower()

        if len(normalized) != 16 or any(c not in "0123456789abcdef" for c in normalized):
            msg = f"SelectionContentHash must be 16 lowercase hex chars, got {dquoted(value)}"
            raise ValueError(msg)
        return normalized


def validate_selection_name(value: str):
    """Raise ValueError if `value` is not a syntactically valid bare selection name."""
    if not _NAME_PATTERN.match(value):
        msg = (
            f"Selection name must start with a letter and contain only letters, "
            f"digits, '_', '-', '.', '/', ':' (max {MAX_SELECTION_NAME_LEN} chars), "
            f"got {dquoted(value)}"
        )
        raise ValueError(msg)


class SelectionName(TypedStr):
    """A bare selection name. Rejects any `@hash` suffix."""

    description = "Selection name"
    pattern = rf"^{NAME_FRAGMENT}$"
    examples = ("my_selection",)

    @override
    @classmethod
    def parse(cls, value: str):
        validate_selection_name(value)
        return value


class SelectionNotFoundError(OntoloomError):
    def __init__(self, name: SelectionName):
        self.name = name
        super().__init__(f"Selection {dquoted(name)} does not exist.")


class WriteMode(StrEnum):
    CREATE = "create"  # refuse if the name is already in use
    REPLACE = "replace"  # overwrite unconditionally


class SelectionExistsError(OntoloomError):
    def __init__(self, name: SelectionName, existing_size: int):
        self.name = name
        self.existing_size = existing_size
        msg = f"Selection {dquoted(name)} already exists ({existing_size} items)."
        super().__init__(msg)


class SelectionKindConflictError(OntoloomError):
    def __init__(self, name: SelectionName):
        self.name = name
        msg = (
            f"Selection {dquoted(name)} already exists as the other kind; "
            f"selection names are unique across axiom and entity selections. "
            f"Remove it first to reuse the name."
        )
        super().__init__(msg)


@dataclass(frozen=True, slots=True)
class AxiomSelection:
    name: SelectionName
    hash: SelectionContentHash
    size: int
    source: str = ""


@dataclass(frozen=True, slots=True)
class AxiomSelectionListing:
    """AxiomSelection plus drift information (how many items still resolve)."""

    meta: AxiomSelection
    present_count: int

    @property
    def missing_count(self) -> int:
        return self.meta.size - self.present_count


@dataclass(frozen=True, slots=True)
class EntitySelection:
    name: SelectionName
    hash: SelectionContentHash
    size: int
    source: str = ""


@dataclass(frozen=True, slots=True)
class EntitySelectionListing:
    """EntitySelection plus drift information (how many items still resolve)."""

    meta: EntitySelection
    present_count: int

    @property
    def missing_count(self) -> int:
        return self.meta.size - self.present_count


@dataclass(frozen=True, slots=True)
class AxiomItem:
    """One row of an axiom selection. `axiom is None` iff the hash no longer resolves."""

    hash: AxiomHash
    axiom: BaseAxiom | None

    @property
    def missing(self) -> bool:
        return self.axiom is None


@dataclass(frozen=True, slots=True)
class EntityItem:
    """One row of an entity selection. `present` is False iff the IRI is unreferenced.

    `roles` holds every role the entity appears in (empty when the IRI is missing
    or carries no role-bearing positions). `label` is populated only when the
    entity is indexed, so it may be None even for present entities.
    """

    iri: IRI
    present: bool
    roles: frozenset[EntityType]
    label: str | None

    @property
    def missing(self) -> bool:
        return not self.present


@dataclass(frozen=True, slots=True)
class AxiomSelectionPage:
    meta: AxiomSelection
    items: tuple[AxiomItem, ...]
    total_filtered: int
    present: int
    missing: int
    show: ShowFilter


@dataclass(frozen=True, slots=True)
class EntitySelectionPage:
    meta: EntitySelection
    items: tuple[EntityItem, ...]
    total_filtered: int
    present: int
    missing: int
    show: ShowFilter
