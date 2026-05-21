"""Selection vocabulary: kinds, ops, validated identifiers, and read-shape DTOs.

Pure types -> no I/O. Persistence lives in `selections/persistence.py`; set-expression
evaluation lives in `selections/compose.py`; paginated reads live in
`selections/read_axiom_selection.py` and `selections/read_entity_selection.py`.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, override

from ontoloom.errors import OntoloomError
from ontoloom.hashing import AxiomHash
from ontoloom.models import TypedStr
from ontoloom.owl.axioms import BaseAxiom
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.utils import dquoted


class SelectionNotFoundError(OntoloomError):
    def __init__(self, name: "SelectionName"):
        self.name = name
        super().__init__(f"Selection {dquoted(name)} does not exist.")


class SelectionKindMismatchError(OntoloomError):
    """Caller's kind-prefixed ref disagrees with the stored selection's kind."""

    def __init__(self, name: "SelectionName", expected: "SelectionKind", actual: "SelectionKind"):
        self.name = name
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Selection {dquoted(name)} is kind {actual}, but caller referenced it as {expected}."
        )


class SelectionExprError(OntoloomError):
    """Set-expression evaluation precondition violated.

    Covers operand-cardinality issues (no operands, too few for intersect/diff)
    and kind mismatches (axioms_for over an axiom expression, mixed-kind operands
    of a set op).
    """


MAX_SELECTION_NAME_LEN = 64

NAME_FRAGMENT = rf"[a-zA-Z][a-zA-Z0-9._/:-]{{0,{MAX_SELECTION_NAME_LEN - 1}}}"

_NAME_PATTERN = re.compile(rf"^{NAME_FRAGMENT}$")


class SelectionKind(StrEnum):
    """Named sets saved from search results for later operations.

    AXIOMS: set of axiom hashes -> scope axiom searches, set algebra, export subsets, mass deletion.
    ENTITIES: set of entity IRIs -> scope entity/axiom searches, set algebra, convert to axiom selections.
    """

    AXIOMS = "axioms"
    ENTITIES = "entities"


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


def _parse_kinded_name(value: str, kind: SelectionKind, type_name: str) -> str:
    """Validate `kind:NAME` wire form; return `value` unchanged."""
    prefix, sep, name = value.partition(":")

    if not sep or prefix != kind.value:
        msg = (
            f"{type_name} must be '{kind.value}:NAME' "
            f"(e.g. '{kind.value}:my_sel'), got {dquoted(value)}"
        )
        raise ValueError(msg)
    validate_selection_name(name)
    return value


class EntitySelectionName(TypedStr):
    """Kind-typed reference to an entity selection. Wire form `entities:NAME`."""

    description = "Entity-kind selection reference (wire form: 'entities:NAME')"
    pattern = rf"^entities:{NAME_FRAGMENT}$"
    examples = ("entities:my_selection",)

    @override
    @classmethod
    def parse(cls, value: str):
        return _parse_kinded_name(value, SelectionKind.ENTITIES, "EntitySelectionName")

    @property
    def bare(self) -> SelectionName:
        return SelectionName(self.removeprefix("entities:"))

    @property
    def kind(self) -> Literal[SelectionKind.ENTITIES]:
        return SelectionKind.ENTITIES


class AxiomSelectionName(TypedStr):
    """Kind-typed reference to an axiom selection. Wire form `axioms:NAME`."""

    description = "Axiom-kind selection reference (wire form: 'axioms:NAME')"
    pattern = rf"^axioms:{NAME_FRAGMENT}$"
    examples = ("axioms:my_selection",)

    @override
    @classmethod
    def parse(cls, value: str):
        return _parse_kinded_name(value, SelectionKind.AXIOMS, "AxiomSelectionName")

    @property
    def bare(self) -> SelectionName:
        return SelectionName(self.removeprefix("axioms:"))

    @property
    def kind(self) -> Literal[SelectionKind.AXIOMS]:
        return SelectionKind.AXIOMS


type SelectionRef = EntitySelectionName | AxiomSelectionName


@dataclass(frozen=True, slots=True)
class SelectionMeta:
    name: SelectionName
    kind: SelectionKind
    hash: SelectionContentHash
    size: int
    source: str = ""


@dataclass(frozen=True, slots=True)
class SelectionListing:
    """SelectionMeta plus drift information (how many items still resolve)."""

    meta: SelectionMeta
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

    `role` and `label` are populated only when the entity is declared (and indexed),
    so they may be None even for present entities.
    """

    iri: IRI
    present: bool
    role: EntityType | None
    label: str | None

    @property
    def missing(self) -> bool:
        return not self.present


@dataclass(frozen=True, slots=True)
class AxiomSelectionPage:
    meta: SelectionMeta
    items: tuple[AxiomItem, ...]
    total_filtered: int
    present: int
    missing: int
    show: ShowFilter


@dataclass(frozen=True, slots=True)
class EntitySelectionPage:
    meta: SelectionMeta
    items: tuple[EntityItem, ...]
    total_filtered: int
    present: int
    missing: int
    show: ShowFilter
