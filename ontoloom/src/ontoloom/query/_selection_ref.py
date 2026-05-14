"""SelectionRef types and resolve_selection — resolve_selection is the lone impure function (DB access); all other exports are pure."""

from dataclasses import dataclass
from typing import override

from ontoloom.connection import Session
from ontoloom.selections.types import (
    _LOCKED_PATTERN,
    LOCKED_PREFIX_MIN,
    SelectionKind,
    SelectionName,
    SelectionNotFoundError,
    StaleSelectionError,
    _validate_name,
)


@dataclass(frozen=True, slots=True)
class SelectionRef:
    """Parsed reference. Carries kind as a typed field.
    Constructed at boundaries: parsed from wire form 'kind:bare_name', or
    built from a selections row. May or may not refer to an existing selection."""

    kind: SelectionKind
    bare_name: str

    @classmethod
    def parse(cls, raw: str) -> "SelectionRef":
        """Split on the FIRST ':' so bare_name may contain further colons.
        Raises ValueError on bad format or invalid bare_name.
        """
        kind_str, sep, bare_name = raw.partition(":")

        if not sep:
            msg = f"SelectionRef must be 'kind:bare_name', got {raw!r}"
            raise ValueError(msg)

        try:
            kind = SelectionKind(kind_str)
        except ValueError:
            msg = f"Unknown selection kind {kind_str!r}; expected one of {[k.value for k in SelectionKind]}"
            raise ValueError(msg) from None

        _validate_name(bare_name)

        return cls(kind=kind, bare_name=bare_name)

    @override
    def __str__(self) -> str:
        return f"{self.kind}:{self.bare_name}"


@dataclass(frozen=True, slots=True)
class ResolvedSelection:
    """A SelectionRef verified to exist. Conventionally constructed via
    resolve_selection; tests may construct directly to skip the DB hit.
    The 'verified' status is convention, not type-system enforced."""

    kind: SelectionKind
    bare_name: str

    @override
    def __str__(self) -> str:
        return f"{self.kind}:{self.bare_name}"


@dataclass(frozen=True, slots=True)
class LockedSelectionRef:
    """SelectionRef plus a lock hash. Wire format 'kind:bare_name@hash_prefix'.
    Used at write boundaries (rename_iri, remove_by_selection)."""

    kind: SelectionKind
    bare_name: str
    hash_prefix: str

    @classmethod
    def parse(cls, raw: str) -> "LockedSelectionRef":
        """Split on first ':' for kind, then rsplit '@' for hash_prefix.
        Bare names may contain ':' but not '@'. Raises ValueError on bad format.
        """
        kind_str, sep, rest = raw.partition(":")

        if not sep:
            msg = f"LockedSelectionRef must be 'kind:bare_name@hash_prefix', got {raw!r}"
            raise ValueError(msg)

        try:
            kind = SelectionKind(kind_str)
        except ValueError:
            msg = f"Unknown selection kind {kind_str!r}; expected one of {[k.value for k in SelectionKind]}"
            raise ValueError(msg) from None

        parts = rest.rsplit("@", 1)

        if len(parts) != 2:
            msg = f"LockedSelectionRef must include '@hash_prefix', got {raw!r}"
            raise ValueError(msg)

        bare_name, hash_prefix = parts

        if not hash_prefix or not _LOCKED_PATTERN.match(hash_prefix):
            msg = (
                f"hash_prefix must be at least {LOCKED_PREFIX_MIN} hex chars, "
                f"got {hash_prefix!r} in {raw!r}"
            )
            raise ValueError(msg)

        _validate_name(bare_name)

        return cls(kind=kind, bare_name=bare_name, hash_prefix=hash_prefix)

    @override
    def __str__(self) -> str:
        return f"{self.kind}:{self.bare_name}@{self.hash_prefix}"


def resolve_selection(s: Session, ref: SelectionRef | LockedSelectionRef) -> ResolvedSelection:
    """Verify existence; verify lock-hash currency when LockedSelectionRef.

    Raises:
        SelectionNotFoundError: if no selection with (kind, bare_name) exists.
        StaleSelectionError: if ref is LockedSelectionRef and hash_prefix no longer matches.
    """
    name = SelectionName(ref.bare_name)
    row = s._conn.execute(
        "SELECT hash, size FROM selections WHERE name = ? AND kind = ?",
        (name, ref.kind),
    ).fetchone()

    if row is None:
        raise SelectionNotFoundError(name)

    if isinstance(ref, LockedSelectionRef):
        current_hash, current_size = row[0], row[1]

        if not current_hash.startswith(ref.hash_prefix):
            raise StaleSelectionError(name, ref.hash_prefix, current_hash, current_size)

    return ResolvedSelection(kind=ref.kind, bare_name=ref.bare_name)
