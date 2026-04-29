import re
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ontoloom.ontology.models.axioms import Axiom
from ontoloom.ontology.models.literals import IRI, EntityType

MatchSource = Literal["iri", "annotation", "list"]
MatchQuality = Literal["exact", "substring"]

MAX_SELECTION_NAME_LEN = 64


def validate_selection_name(v: str):
    """Validate a selection name. Used by both SelectionName and LockedSelection."""
    if not v:
        msg = "Selection name must not be empty."
        raise ValueError(msg)
    if "@" in v:
        msg = "Selection names must not contain '@'."
        raise ValueError(msg)
    if len(v) > MAX_SELECTION_NAME_LEN:
        msg = f"Selection name too long ({len(v)} chars, max {MAX_SELECTION_NAME_LEN})."
        raise ValueError(msg)
    return v


_LOCKED_SELECTION_RE = re.compile(r"^([^@]+)@([0-9a-fA-F]+)$")


class LockedSelection(str):
    """A selection reference with optimistic-locking hash: `name@hash_prefix`.

    Required for write operations that act on a selection. The hash prefix
    verifies the selection hasn't changed since the caller last observed it.

    Examples:
        LockedSelection("my_sel@a3f1") → my_sel@a3f1
    """

    def __new__(cls, value: str):
        m = _LOCKED_SELECTION_RE.match(value)
        if not m:
            msg = (
                f"LockedSelection must be in 'name@hash_prefix' format "
                f"(e.g. 'my_sel@a3f1'), got {value!r}"
            )
            raise ValueError(msg)
        validate_selection_name(m.group(1))
        return super().__new__(cls, value)

    @property
    def name(self) -> str:
        return self.split("@", 1)[0]

    @property
    def hash_prefix(self) -> str:
        return self.split("@", 1)[1]

    def __repr__(self):
        return f"LockedSelection({self})"

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema())

    @classmethod
    def __get_pydantic_json_schema__(cls, schema: Any, handler: Any) -> dict[str, Any]:
        return {
            "type": "string",
            "description": (
                "Selection reference with optimistic locking, in 'name@hash_prefix' format"
            ),
            "pattern": r"^[^@]+@[0-9a-fA-F]+$",
            "examples": ["my_selection@a3f1"],
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


@dataclass(frozen=True)
class SelectionMeta:
    name: str
    kind: SelectionKind
    hash: str
    cardinality: int
    source: str = ""


@dataclass(frozen=True)
class SelectionItem:
    key: str
    missing: bool
    axiom: Axiom | None = None
    role: str | None = None
    label: str | None = None


@dataclass(frozen=True)
class SelectionPage:
    meta: SelectionMeta
    items: list[SelectionItem] = field(default_factory=list)
    total_filtered: int = 0
    present: int = 0
    missing: int = 0
    show: ShowFilter = ShowFilter.ALL


@dataclass
class AnnotationRow:
    property: IRI
    value: str


@dataclass
class EntityInfo:
    roles: set[EntityType]
    annotations: list[AnnotationRow]
    axiom_counts: Counter[str]


@dataclass
class EntityMatch:
    iri: IRI
    roles: set[EntityType]
    annotations: list[AnnotationRow]
    match_source: MatchSource
    match_quality: MatchQuality


@dataclass
class EntitySearchPage:
    matches: list[EntityMatch]
    total: int


@dataclass
class HashedAxiom:
    axiom: Axiom
    hash: str


@dataclass
class AddResult:
    added: list[HashedAxiom]
    skipped: list[HashedAxiom]


@dataclass
class RemoveResult:
    removed: list[HashedAxiom]


@dataclass
class DuplicateResult:
    groups: list[tuple[str, list[str]]]
    total_groups: int
    affected_iris: list[str]


@dataclass
class ReplaceResult:
    old_hash: str
    new_hash: str
    was_noop: bool  # True if new_hash == old_hash


@dataclass
class RenameResult:
    old_iri: str
    new_iri: str
    replaced: list[ReplaceResult]
    batch_id: str
