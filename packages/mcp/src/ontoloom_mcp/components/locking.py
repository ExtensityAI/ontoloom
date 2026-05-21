"""Optimistic-locking selection refs and `verify_lock` for MCP write tools.

Locking is an LLM-context-staleness mitigation, not a core database integrity
mechanism. It lives here so the core library stays free of hash-prefix
plumbing on its mutation signatures; multi-process callers should use real
transactions, not hash prefixes, for concurrency control.
"""

import re
from typing import Literal, overload, override

from ontoloom.connection import Session
from ontoloom.errors import OntoloomError
from ontoloom.models import TypedStr
from ontoloom.selections.persistence import get_selection
from ontoloom.selections.types import (
    NAME_FRAGMENT,
    AxiomSelectionName,
    EntitySelectionName,
    SelectionContentHash,
    SelectionKind,
    SelectionMeta,
    SelectionName,
    SelectionNotFoundError,
    validate_selection_name,
)
from ontoloom.utils import dquoted

LOCKED_PREFIX_MIN = 8

_HASH_FRAGMENT = rf"[0-9a-fA-F]{{{LOCKED_PREFIX_MIN},}}"
_HASH_PATTERN = re.compile(rf"^{_HASH_FRAGMENT}$")


class HashPrefix(TypedStr):
    """Hex hash prefix, lowercase, at least `LOCKED_PREFIX_MIN` chars."""

    description = f"Hash prefix ({LOCKED_PREFIX_MIN}+ hex chars)"
    pattern = rf"^{_HASH_FRAGMENT}$"
    examples = ("a3f1b2c4",)

    @override
    @classmethod
    def parse(cls, value: str):
        if not _HASH_PATTERN.match(value):
            msg = f"HashPrefix must be at least {LOCKED_PREFIX_MIN} hex chars, got {dquoted(value)}"
            raise ValueError(msg)
        return value


class StaleSelectionError(OntoloomError):
    """Selection has changed since the caller last observed it."""

    def __init__(
        self,
        name: SelectionName,
        supplied_prefix: HashPrefix,
        current_hash: SelectionContentHash | None,
        current_size: int | None = None,
    ):
        self.name = name
        self.supplied_prefix = supplied_prefix
        self.current_hash = current_hash
        self.current_size = current_size
        current = current_hash if current_hash else "<absent>"
        super().__init__(
            f"Selection {dquoted(name)} has changed (your prefix: {dquoted(supplied_prefix)}, "
            f"current hash: {dquoted(current)}). Re-read the selection to get the current hash."
        )


def _parse_kinded_locked(value: str, kind: SelectionKind, type_name: str) -> str:
    """Validate `kind:NAME@HASH_PREFIX` wire form; lowercase the hash portion."""
    prefix, sep, rest = value.partition(":")

    if not sep or prefix != kind.value:
        msg = f"{type_name} must be '{kind.value}:NAME@HASH_PREFIX', got {dquoted(value)}"
        raise ValueError(msg)

    name, at_sep, hash_prefix = rest.partition("@")

    if not at_sep or not _HASH_PATTERN.match(hash_prefix):
        msg = (
            f"{type_name} must include '@HASH_PREFIX' "
            f"(>= {LOCKED_PREFIX_MIN} hex chars), got {dquoted(value)}"
        )
        raise ValueError(msg)
    validate_selection_name(name)
    return f"{prefix}:{name}@{hash_prefix.lower()}"


class LockedEntitySelectionName(TypedStr):
    """Locked entity selection ref. Wire form `entities:NAME@HASH_PREFIX`."""

    description = "Locked entity selection (wire: 'entities:NAME@HASH_PREFIX')"
    pattern = rf"^entities:{NAME_FRAGMENT}@{_HASH_FRAGMENT}$"
    examples = ("entities:my_selection@a3f1b2c4",)

    @override
    @classmethod
    def parse(cls, value: str):
        return _parse_kinded_locked(value, SelectionKind.ENTITIES, "LockedEntitySelectionName")

    @property
    def bare(self) -> EntitySelectionName:
        wire, _, _ = self.partition("@")
        return EntitySelectionName(wire)

    @property
    def hash_prefix(self) -> HashPrefix:
        _, _, suffix = self.partition("@")
        return HashPrefix(suffix)

    @property
    def kind(self) -> Literal[SelectionKind.ENTITIES]:
        return SelectionKind.ENTITIES


class LockedAxiomSelectionName(TypedStr):
    """Locked axiom selection ref. Wire form `axioms:NAME@HASH_PREFIX`."""

    description = "Locked axiom selection (wire: 'axioms:NAME@HASH_PREFIX')"
    pattern = rf"^axioms:{NAME_FRAGMENT}@{_HASH_FRAGMENT}$"
    examples = ("axioms:my_selection@a3f1b2c4",)

    @override
    @classmethod
    def parse(cls, value: str):
        return _parse_kinded_locked(value, SelectionKind.AXIOMS, "LockedAxiomSelectionName")

    @property
    def bare(self) -> AxiomSelectionName:
        wire, _, _ = self.partition("@")
        return AxiomSelectionName(wire)

    @property
    def hash_prefix(self) -> HashPrefix:
        _, _, suffix = self.partition("@")
        return HashPrefix(suffix)

    @property
    def kind(self) -> Literal[SelectionKind.AXIOMS]:
        return SelectionKind.AXIOMS


type LockedSelectionRef = LockedEntitySelectionName | LockedAxiomSelectionName


@overload
def verify_lock(s: Session, locked: LockedEntitySelectionName) -> EntitySelectionName: ...
@overload
def verify_lock(s: Session, locked: LockedAxiomSelectionName) -> AxiomSelectionName: ...


def verify_lock(s: Session, locked: LockedSelectionRef):
    """Verify `locked` references a current selection; return its narrow bare form.

    Raises:
        SelectionNotFoundError: no `(name, kind)` row exists.
        StaleSelectionError: row exists but its current hash doesn't start with
            `locked.hash_prefix`.
    """
    bare = locked.bare
    name = bare.bare
    meta = get_selection(s, name)

    if meta.kind != locked.kind:
        raise SelectionNotFoundError(name)

    if not meta.hash.startswith(locked.hash_prefix):
        raise StaleSelectionError(name, locked.hash_prefix, meta.hash, meta.size)

    return bare


def format_locked_quoted(meta: SelectionMeta) -> str:
    """Render `meta` as a double-quoted wire-form locked ref for embedding in MCP messages."""
    return dquoted(f"{meta.kind}:{meta.name}@{meta.hash}")
