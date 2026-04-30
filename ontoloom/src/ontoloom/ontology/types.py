# Shared lightweight types used across core and MCP layers; no business logic.
# Intentional grab-bag: selection DTOs, entity types, axiom helpers.
import re
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal, override

from ontoloom.ontology.errors import BadRequestError
from ontoloom.ontology.models._pydantic import _PydanticStr
from ontoloom.ontology.models.base import BaseAxiom
from ontoloom.ontology.models.literals import IRI, EntityType

# A: look through this file, there are lots of types that maybe should be colocated with their functions, or located elsewhere - this seems like a bit of a lazy approach. for each of these, check where it shoudl actually be, it might be that some need to be in new files etc etc

# A global: also, rethink all these types - which ones are good, which ones are bad? which to improve or simplify? for each, figure out where they are needed and for what, etc.


class SetOp(StrEnum):
    UNION = "union"
    INTERSECTION = "intersection"
    DIFFERENCE = "difference"


class ConversionOp(StrEnum):
    AXIOMS_FOR = "axioms_for"
    ENTITIES_IN = "entities_in"


MatchSource = Literal[
    "iri", "annotation", "list"
]  # A global: should these not be str enums? maybe check everywhere, but it might be okay depending on the case, so please judge each
MatchQuality = Literal["exact", "substring"]

MAX_SELECTION_NAME_LEN = 64

# A: not sure but checking for control chars seems so weird to me?
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def validate_selection_name(v: str):
    """Validate a selection name. Used by both SelectionName and LockedSelection."""
    if not v:
        msg = "Selection name must not be empty."
        raise BadRequestError(msg)
    if "@" in v:
        msg = "Selection names must not contain '@'."
        raise BadRequestError(msg)
    if _CONTROL_CHARS.search(v):
        msg = "Selection name must not contain control characters (NUL, newline, tab, etc.)."
        raise BadRequestError(msg)
    if len(v) > MAX_SELECTION_NAME_LEN:
        msg = f"Selection name too long ({len(v)} chars, max {MAX_SELECTION_NAME_LEN})."
        raise BadRequestError(msg)
    return v


_HASH_PREFIX_RE = re.compile(r"^[0-9a-fA-F]{8,}$")


class LockedSelection(_PydanticStr):
    """A selection reference with optimistic-locking hash: `name@hash_prefix`.

    Used for `within=` on tools whose operation mutates the scoped selection
    (remove_axioms, rename_iri). The hash prefix verifies the selection hasn't
    changed since the caller last observed it.

    Read-only or output-only selection parameters use bare `SelectionName`
    instead. find_duplicates writes a selection but does NOT mutate its
    `within=` scope, so it takes `SelectionName`.

    Read paths (`summary`, `describe_ontology`, `read_selection`) deliberately
    do not require a hash prefix — they always reflect current state, and any
    "staleness" is observable on the next read. Locking is for write paths,
    where the caller's intent depends on a known prior state.

    Examples:
        LockedSelection("my_sel@a3f1") -> my_sel@a3f1
    """

    def __new__(cls, value: str):
        name, sep, hash_prefix = value.partition("@")
        if not sep or not _HASH_PREFIX_RE.match(hash_prefix):
            msg = (
                f"LockedSelection must be in 'name@hash_prefix' format with at least 8 hex "
                f"characters in the prefix (e.g. 'my_sel@a3f1b2c4'), got {value!r}"
            )
            raise ValueError(msg)
        validate_selection_name(name)
        return super().__new__(cls, value)

    @property
    def name(self) -> str:
        return self.split("@", 1)[0]

    @property
    def hash_prefix(self) -> str:
        return self.split("@", 1)[1]

    @override
    def __repr__(self):
        return f"LockedSelection({self})"

    @classmethod
    def __get_pydantic_json_schema__(cls, schema: Any, handler: Any) -> dict[str, Any]:
        return {
            "type": "string",
            "description": (
                "Selection reference with optimistic locking, in 'name@hash_prefix' format"
            ),
            "pattern": r"^[^@]+@[0-9a-fA-F]{8,}$",
            "examples": ["my_selection@a3f1b2c4"],
        }


class SelectionKind(StrEnum):
    """Named sets saved from search results for later operations.

    AXIOMS: set of axiom hashes — scope axiom searches, set algebra, export subsets, mass deletion.
    ENTITIES: set of entity IRIs — scope entity/axiom searches, set algebra, convert to axiom selections.
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


@dataclass(frozen=True, slots=True)
class SelectionMeta:
    name: str
    kind: SelectionKind
    hash: str
    cardinality: int
    source: str = ""


@dataclass(frozen=True, slots=True)
class SelectionItem:
    key: str
    missing: bool
    axiom: BaseAxiom | None = None
    role: str | None = None
    label: str | None = None


@dataclass(frozen=True, slots=True)
class SelectionPage:
    meta: SelectionMeta
    items: list[SelectionItem] = field(default_factory=list)
    total_filtered: int = 0
    present: int = 0
    missing: int = 0
    show: ShowFilter = ShowFilter.ALL


@dataclass(frozen=True, slots=True)
class AnnotationRow:
    property: IRI
    value: str


@dataclass(frozen=True, slots=True)
class AxiomSummary:
    total: int
    by_type: Counter[str]


@dataclass(frozen=True, slots=True)
class EntitySummary:
    total: int
    by_role: Counter[str]


@dataclass(frozen=True, slots=True)
class EntityInfo:
    roles: set[EntityType]
    annotations: list[AnnotationRow]
    axiom_counts: Counter[str]


@dataclass(frozen=True, slots=True)
class EntityMatch:
    iri: IRI
    roles: set[EntityType]
    annotations: list[AnnotationRow]
    match_source: MatchSource
    match_quality: MatchQuality


@dataclass(frozen=True, slots=True)
class EntitySearchPage:
    matches: list[EntityMatch]
    total: int


@dataclass(frozen=True, slots=True)
class HashedAxiom:
    axiom: BaseAxiom
    hash: str


@dataclass(frozen=True, slots=True)
class AddResult:
    added: list[HashedAxiom]
    skipped: list[HashedAxiom]


@dataclass(frozen=True, slots=True)
class RemoveResult:
    removed: list[HashedAxiom]


@dataclass(frozen=True, slots=True)
class RemoveBySelectionResult:
    removed: list[HashedAxiom]
    absent: int


@dataclass(frozen=True, slots=True)
class UpsertSelectionResult:
    content_hash: str
    cardinality: int
    old_cardinality: int | None


@dataclass(frozen=True, slots=True)
class DroppedSelection:
    name: str
    cardinality: int


@dataclass(frozen=True, slots=True)
class RemoveSelectionsResult:
    dropped: list[DroppedSelection]
    not_found: list[str]


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    value: str
    iris: list[str]


@dataclass(frozen=True, slots=True)
class DuplicateResult:
    groups: list[DuplicateGroup]
    total_groups: int
    affected_iris: list[str]


@dataclass(frozen=True, slots=True)
class ReplaceResult:
    old: HashedAxiom
    new: HashedAxiom
    was_noop: bool  # True if new.hash == old.hash
    was_merged_into_existing: bool = False  # True if new_hash collided with another existing axiom

    @property
    def old_hash(self) -> str:
        return self.old.hash

    @property
    def new_hash(self) -> str:
        return self.new.hash


@dataclass(frozen=True, slots=True)
class RenameResult:
    old_iri: str
    new_iri: str
    replaced: list[ReplaceResult]
    batch_id: str
