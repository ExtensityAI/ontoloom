"""Selection vocabulary: kinds, ops, validated identifiers, and read-shape DTOs.

Pure types -> no I/O. Persistence and operations live in `selections/store.py`.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import override

from ontoloom.models import TypedStr
from ontoloom.owl.axioms import BaseAxiom

MAX_SELECTION_NAME_LEN = 64
LOCKED_PREFIX_MIN = 8

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_LOCKED_PATTERN = re.compile(rf"^[0-9a-fA-F]{{{LOCKED_PREFIX_MIN},}}$")


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


class ConversionOp(StrEnum):
    AXIOMS_FOR = "axioms_for"
    ENTITIES_IN = "entities_in"


def _validate_name(value: str):
    if not value:
        msg = "Selection name must not be empty."
        raise ValueError(msg)
    if "@" in value:
        msg = "Selection name must not contain '@'."
        raise ValueError(msg)
    if _CONTROL_CHARS.search(value):
        msg = "Selection name must not contain control characters (NUL, newline, tab, etc.)."
        raise ValueError(msg)
    if len(value) > MAX_SELECTION_NAME_LEN:
        msg = f"Selection name too long ({len(value)} chars, max {MAX_SELECTION_NAME_LEN})."
        raise ValueError(msg)


class SelectionName(TypedStr):
    """A validated selection name -> no '@', no control chars, max 64 chars, non-empty."""

    description = "Selection name"
    examples = ("my_selection", "candidates_v2")

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

    Examples:
        LockedSelection("my_sel@a3f1b2c4") -> my_sel@a3f1b2c4
    """

    description = "Selection reference with optimistic locking, in 'name@hash_prefix' format"
    pattern = rf"^[^@]+@[0-9a-fA-F]{{{LOCKED_PREFIX_MIN},}}$"
    examples = ("my_selection@a3f1b2c4",)

    @override
    @classmethod
    def parse(cls, value: str):
        name, sep, hash_prefix = value.partition("@")

        if not sep or not _LOCKED_PATTERN.match(hash_prefix):
            msg = (
                f"LockedSelection must be 'name@hash_prefix' with at least "
                f"{LOCKED_PREFIX_MIN} hex chars (e.g. 'my_sel@a3f1b2c4'), got {value!r}"
            )
            raise ValueError(msg)
        _validate_name(name)
        return value

    @property
    def name(self):
        return SelectionName(self.split("@", 1)[0])

    @property
    def hash_prefix(self):
        return self.split("@", 1)[1]


@dataclass(frozen=True, slots=True)
class SelectionMeta:
    name: str
    kind: SelectionKind
    hash: str
    size: int
    source: str = ""

    @property
    def locked(self):
        return f"{self.name}@{self.hash}"

    @override
    def __str__(self):
        return self.locked


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
