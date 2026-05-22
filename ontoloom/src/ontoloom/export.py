from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from ontoloom.connection import (
    CURRENT_SCHEMA_VERSION,
    Session,
    assert_within_workspace,
)
from ontoloom.prefixes.store import list_prefixes
from ontoloom.prefixes.types import NamespaceIRI, PrefixName
from ontoloom.query.constraints import AxiomConstraint, InSelection
from ontoloom.query.dispatch import run
from ontoloom.query.stream_axioms import StreamAxioms
from ontoloom.selections.store import get_selection
from ontoloom.selections.types import AxiomSelectionName
from ontoloom.utils import dquoted

FORMAT_VERSION = 4


class HeaderRecord(BaseModel, frozen=True):
    format: Literal["ontoloom-jsonl"]
    format_version: int
    schema_version: int
    exported_at: str
    prefixes: dict[PrefixName, NamespaceIRI]


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Outcome of `export_jsonl`. `skipped` is non-zero only when scoping by
    a selection that contains hashes no longer in the store."""

    exported: int
    skipped: int


def export_jsonl(
    s: Session, output_path: Path, *, within: AxiomSelectionName | None = None
) -> ExportResult:
    """Export axioms as JSONL with a header line."""
    assert_within_workspace(output_path)

    if not output_path.parent.exists():
        msg = f"Directory {dquoted(output_path.parent)} does not exist."
        raise FileNotFoundError(msg)

    selection_size: int | None = None
    constraints: list[AxiomConstraint] = []

    if within is not None:
        meta = get_selection(s, within.bare)
        selection_size = meta.size
        constraints.append(InSelection(ref=within))

    header = HeaderRecord(
        format="ontoloom-jsonl",
        format_version=FORMAT_VERSION,
        schema_version=CURRENT_SCHEMA_VERSION,
        exported_at=datetime.now(UTC).isoformat(),
        prefixes=list_prefixes(s),
    )

    count = 0
    with output_path.open("w") as f:
        f.write(header.model_dump_json())
        f.write("\n")
        with run(s, StreamAxioms(constraints=tuple(constraints))) as it:
            for _h, json_text in it:
                f.write(json_text)
                f.write("\n")
                count += 1

    skipped = 0 if selection_size is None else selection_size - count
    return ExportResult(exported=count, skipped=skipped)
