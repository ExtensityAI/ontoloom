"""Incremental operation editing — surgically fix reviewer-flagged issues."""

import json
import secrets
from typing import Annotated, Literal, cast

from pydantic import Field
from symai import Expression
from symai.strategy import contract

from ontology_hydra.config import ComponentName, HydraConfig
from ontology_hydra.llm.engine import create_component_engine
from ontology_hydra.ontology.components.implementation.draft_ops import OperationSequence
from ontology_hydra.ontology.models import Ontology
from ontology_hydra.ontology.revision.executor import execute_ops
from ontology_hydra.ontology.revision.operations import Operation
from ontology_hydra.utils.schema.models import DataModel


# ---------------------------------------------------------------------------
# Edit action models (discriminated union on "action")
# ---------------------------------------------------------------------------


class Append(DataModel):
    action: Literal["append"] = "append"
    ops: list[Operation] = Field(description="Operations to append at the end.")


class Prepend(DataModel):
    action: Literal["prepend"] = "prepend"
    ops: list[Operation] = Field(description="Operations to prepend at the beginning.")


class InsertAfter(DataModel):
    action: Literal["insert_after"] = "insert_after"
    ref: str = Field(description="Ref tag of the operation to insert after.")
    ops: list[Operation] = Field(description="Operations to insert.")


class InsertBefore(DataModel):
    action: Literal["insert_before"] = "insert_before"
    ref: str = Field(description="Ref tag of the operation to insert before.")
    ops: list[Operation] = Field(description="Operations to insert.")


class Remove(DataModel):
    action: Literal["remove"] = "remove"
    start_ref: str = Field(description="Ref tag of the first operation to remove.")
    end_ref: str | None = Field(
        None,
        description="Ref tag of the last operation to remove (inclusive). None = single op.",
    )


class Replace(DataModel):
    action: Literal["replace"] = "replace"
    start_ref: str = Field(description="Ref tag of the first operation to replace.")
    end_ref: str | None = Field(
        None,
        description="Ref tag of the last operation to replace (inclusive). None = single op.",
    )
    ops: list[Operation] = Field(description="Replacement operations.")


EditAction = Annotated[
    Append | Prepend | InsertAfter | InsertBefore | Remove | Replace,
    Field(discriminator="action"),
]


class EditSequence(DataModel):
    edits: list[EditAction] = Field(
        description="Sequence of edit actions to apply to the previous operations.",
    )


# ---------------------------------------------------------------------------
# Ref tagging
# ---------------------------------------------------------------------------


def _tag_ops_with_refs(
    ops: list[Operation],
) -> tuple[list[dict], dict[str, int]]:
    """Assign a 4-char hex ref to each op. Returns (tagged_dicts, ref_to_index)."""
    tagged: list[dict] = []
    ref_map: dict[str, int] = {}
    for i, op in enumerate(ops):
        ref = secrets.token_hex(2)
        d = op.model_dump(mode="json", exclude_none=True)
        d["_ref"] = ref
        tagged.append(d)
        ref_map[ref] = i
    return tagged, ref_map


# ---------------------------------------------------------------------------
# Edit resolution
# ---------------------------------------------------------------------------


class EditResolutionError(Exception):
    """Raised when an edit sequence cannot be applied."""


def _resolve_ref(ref: str, ref_map: dict[str, int], label: str = "ref") -> int:
    if ref not in ref_map:
        msg = f"Unknown {label} '{ref}'"
        raise EditResolutionError(msg)
    return ref_map[ref]


def _resolve_range(
    start_ref: str,
    end_ref: str | None,
    ref_map: dict[str, int],
) -> tuple[int, int]:
    start = _resolve_ref(start_ref, ref_map, "start_ref")
    if end_ref is None:
        return start, start
    end = _resolve_ref(end_ref, ref_map, "end_ref")
    if end < start:
        msg = f"Reversed range: start_ref '{start_ref}' (index {start}) > end_ref '{end_ref}' (index {end})"
        raise EditResolutionError(msg)
    return start, end


def apply_edits(
    previous_ops: list[Operation],
    edits: list[EditAction],
    ref_map: dict[str, int],
) -> list[Operation]:
    """Apply an edit sequence to the previous operation list.

    Raises EditResolutionError on invalid refs, overlapping destructive ranges, etc.
    """
    # 1. Classify edits
    destructive: list[Remove | Replace] = []
    inserts_after: list[InsertAfter] = []
    inserts_before: list[InsertBefore] = []
    appends: list[Append] = []
    prepends: list[Prepend] = []

    for edit in edits:
        match edit:
            case Remove() | Replace():
                destructive.append(edit)
            case InsertAfter():
                inserts_after.append(edit)
            case InsertBefore():
                inserts_before.append(edit)
            case Append():
                appends.append(edit)
            case Prepend():
                prepends.append(edit)

    # 2. Resolve destructive ranges and check for overlaps
    destroyed: list[tuple[int, int, Remove | Replace]] = []
    for edit in destructive:
        start, end = _resolve_range(edit.start_ref, edit.end_ref, ref_map)
        destroyed.append((start, end, edit))

    destroyed.sort(key=lambda t: t[0])
    for i in range(len(destroyed) - 1):
        _, end_a, _ = destroyed[i]
        start_b, _, _ = destroyed[i + 1]
        if start_b <= end_a:
            msg = f"Overlapping destructive ranges: one ends at index {end_a}, next starts at {start_b}"
            raise EditResolutionError(msg)

    # Collect all removed indices
    removed_indices: set[int] = set()
    for start, end, _ in destroyed:
        removed_indices.update(range(start, end + 1))

    # 3. Validate insert refs don't point to removed ops
    for edit in inserts_after:
        idx = _resolve_ref(edit.ref, ref_map, "insert_after ref")
        if idx in removed_indices:
            msg = f"insert_after ref '{edit.ref}' targets a removed operation (index {idx})"
            raise EditResolutionError(msg)
    for edit in inserts_before:
        idx = _resolve_ref(edit.ref, ref_map, "insert_before ref")
        if idx in removed_indices:
            msg = f"insert_before ref '{edit.ref}' targets a removed operation (index {idx})"
            raise EditResolutionError(msg)

    # 4. Apply destructive edits in reverse order (so splicing doesn't shift earlier indices)
    result = list(previous_ops)
    for start, end, edit in reversed(destroyed):
        replacement = edit.ops if isinstance(edit, Replace) else []
        result[start : end + 1] = replacement

    # 5. Build orig_to_new index remap for surviving ops
    orig_to_new: dict[int, int] = {}
    new_idx = 0
    for orig_idx in range(len(previous_ops)):
        if orig_idx in removed_indices:
            # For replaced ranges, skip — replacements are already spliced in
            # Find which destructive edit covers this index
            for start, end, edit in destroyed:
                if start <= orig_idx <= end:
                    if isinstance(edit, Replace) and orig_idx == start:
                        # Map the start of a replaced range to where the replacements begin
                        orig_to_new[orig_idx] = new_idx
                        new_idx += len(edit.ops)
                    elif isinstance(edit, Replace) and orig_idx > start:
                        pass  # already counted
                    else:
                        pass  # Remove — nothing added
                    break
        else:
            orig_to_new[orig_idx] = new_idx
            new_idx += 1

    # 6. Apply inserts in reverse resolved-position order
    all_inserts: list[tuple[int, bool, list[Operation]]] = []  # (position, is_before, ops)
    for edit in inserts_after:
        orig = _resolve_ref(edit.ref, ref_map, "insert_after ref")
        pos = orig_to_new[orig]
        all_inserts.append((pos, False, edit.ops))
    for edit in inserts_before:
        orig = _resolve_ref(edit.ref, ref_map, "insert_before ref")
        pos = orig_to_new[orig]
        all_inserts.append((pos, True, edit.ops))

    # Sort by position descending so we insert from back to front
    # For same position: before inserts go before after inserts
    all_inserts.sort(key=lambda t: (t[0], not t[1]), reverse=True)

    for pos, is_before, ops in all_inserts:
        insert_at = pos if is_before else pos + 1
        result[insert_at:insert_at] = ops

    # 7. Apply prepends (reversed) then appends
    for edit in reversed(prepends):
        result[0:0] = edit.ops
    for edit in appends:
        result.extend(edit.ops)

    return result


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_prompt = """You are an ontology engineer. A previous attempt at generating operations was rejected by review. \
Your job is to surgically edit the operation sequence to fix the issues — not rewrite from scratch.

<intent>{intent}</intent>
<plan>{plan}</plan>
<ontology>{ontology}</ontology>

<previous_operations>
{tagged_ops}
</previous_operations>

<review_feedback>
{feedback}
</review_feedback>

Each operation above has a "_ref" tag (4-char hex). Use these refs to target your edits.

Available edit actions:
- append: add operations at the end
- prepend: add operations at the beginning
- insert_after: insert operations after the referenced op
- insert_before: insert operations before the referenced op
- remove: remove one op (start_ref only) or a contiguous range (start_ref + end_ref, inclusive)
- replace: replace one op or a contiguous range with new operations

Rules:
- Only edit what the feedback criticises. Preserve correct operations.
- Ensure operation ordering still satisfies dependencies (classes before properties that reference them).
- Use exact class/property names from the ontology for existing entities.
- Follow naming conventions: PascalCase for classes, camelCase for properties."""


# ---------------------------------------------------------------------------
# Expression
# ---------------------------------------------------------------------------


class _Input(DataModel):
    ontology: Ontology


@contract(accumulate_errors=True, post_remedy=True)
class ReviseOps(Expression):
    def __init__(
        self,
        plan: str,
        intent: str,
        ontology: Ontology,
        previous_ops: list[Operation],
        feedback: str,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._plan = plan
        self._intent = intent
        self._ontology = ontology
        self._previous_ops = previous_ops
        self._feedback = feedback
        self._tagged_ops, self._ref_map = _tag_ops_with_refs(previous_ops)
        self._resolved_ops: list[Operation] | None = None

    def forward(self, _: _Input) -> EditSequence:  # pyright: ignore[reportIncompatibleMethodOverride]
        if self.contract_result is None:
            msg = "Contract failed!"
            raise ValueError(msg)
        return self.contract_result

    def post(self, edit_seq: EditSequence):
        resolved = apply_edits(self._previous_ops, edit_seq.edits, self._ref_map)
        execute_ops(self._ontology, resolved)
        self._resolved_ops = resolved
        return True

    @property
    def prompt(self):  # pyright: ignore[reportIncompatibleMethodOverride]
        return _prompt.format(
            plan=self._plan,
            intent=self._intent,
            ontology=self._ontology.model_dump_json(),
            tagged_ops=json.dumps(self._tagged_ops, indent=2),
            feedback=self._feedback,
        )


def revise_ops(
    config: HydraConfig,
    plan: str,
    intent: str,
    ontology: Ontology,
    previous_ops: OperationSequence,
    *,
    feedback: str,
) -> OperationSequence:
    reviser = cast(
        "ReviseOps",
        ReviseOps(plan, intent, ontology, previous_ops.ops, feedback),
    )
    with create_component_engine(config, ComponentName.revise_ops):
        reviser(_Input(ontology=ontology))

    assert reviser._resolved_ops is not None
    return OperationSequence(ops=reviser._resolved_ops)
