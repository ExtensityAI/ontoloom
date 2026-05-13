"""Selection vocabulary: kinds, ops, validated identifiers, and read-shape DTOs.

Pure types -> no I/O. Persistence and operations live in `selections/store.py`.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import override

from ontoloom.hashing import AxiomHash
from ontoloom.models import TypedStr
from ontoloom.owl.axioms import BaseAxiom
from ontoloom.owl.iri import IRI
from ontoloom.owl.markers import EntityType
from ontoloom.utils import dquoted

MAX_SELECTION_NAME_LEN = 64
LOCKED_PREFIX_MIN = 8

# Pattern fragments — single source of truth, composed by SelectionName /
# LockedSelection regexes and JSON-schema patterns.
_NAME_FRAGMENT = rf"[a-zA-Z][a-zA-Z0-9._/:-]{{0,{MAX_SELECTION_NAME_LEN - 1}}}"
_HASH_FRAGMENT = rf"[0-9a-fA-F]{{{LOCKED_PREFIX_MIN},}}"

_NAME_PATTERN = re.compile(rf"^{_NAME_FRAGMENT}$")
_LOCKED_PATTERN = re.compile(rf"^{_HASH_FRAGMENT}$")


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


def _validate_name(value: str):
    if not _NAME_PATTERN.match(value):
        msg = (
            f"Selection name must start with a letter and contain only letters, "
            f"digits, '_', '-', '.', '/', ':' (max {MAX_SELECTION_NAME_LEN} chars), "
            f"got {dquoted(value)}"
        )
        raise ValueError(msg)


class SelectionName(TypedStr):
    """A bare selection name. Rejects any `@hash` suffix.

    Used for `within=` on read tools, where reads always reflect current state.
    Write tools that need optimistic locking on the scoped selection use
    `LockedSelection`, which carries the hash and enforces it.
    """

    description = "Selection name"
    pattern = rf"^{_NAME_FRAGMENT}$"
    examples = ("my_selection",)

    @override
    @classmethod
    def parse(cls, value: str):
        _validate_name(value)
        return value


class LockedSelection(TypedStr):
    """A selection reference with optimistic-locking hash: `name@hash_prefix`.

    Used for `within=` on tools whose operation mutates the scoped selection
    (remove_axioms, rename_iri). The hash prefix verifies the selection hasn't
    changed since the caller last observed it.

    Read paths take bare `SelectionName` and always reflect current state.

    The decomposed parts (`name`, `hash_prefix`) are computed once at
    construction and cached as instance attributes — no re-parsing on access.

    Examples:
        LockedSelection("my_sel@a3f1b2c4") -> my_sel@a3f1b2c4
    """

    description = "Selection reference with optimistic locking, in 'name@hash_prefix' format"
    pattern = rf"^{_NAME_FRAGMENT}@{_HASH_FRAGMENT}$"
    examples = ("my_selection@a3f1b2c4",)

    name: SelectionName
    hash_prefix: str

    @override
    @classmethod
    def parse(cls, value: str):
        name, sep, hash_prefix = value.partition("@")

        if not sep or not _LOCKED_PATTERN.match(hash_prefix):
            msg = (
                f"LockedSelection must be 'name@hash_prefix' with at least "
                f"{LOCKED_PREFIX_MIN} hex chars (e.g. 'my_sel@a3f1b2c4'), got {dquoted(value)}"
            )
            raise ValueError(msg)
        _validate_name(name)
        return value

    @override
    def __new__(cls, value: str):
        inst = super().__new__(cls, value)
        name, _, hash_prefix = inst.partition("@")
        inst.name = SelectionName(name)
        inst.hash_prefix = hash_prefix
        return inst


@dataclass(frozen=True, slots=True)
class SelectionMeta:
    name: SelectionName
    kind: SelectionKind
    hash: SelectionContentHash
    size: int
    source: str = ""

    @property
    def locked(self):
        return f"{self.name}@{self.hash}"

    @override
    def __str__(self):
        return self.locked


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
