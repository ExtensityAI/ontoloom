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
from ontoloom.prefixes import NamespaceIRI, PrefixName, list_prefixes
from ontoloom.selections.store import SelectionKindError, get_selection
from ontoloom.selections.types import SelectionKind, SelectionName

FORMAT_VERSION = 4


class HeaderRecord(BaseModel, frozen=True):
    format: Literal["ontoloom-jsonl"]
    format_version: int
    schema_version: int
    exported_at: str
    prefixes: dict[PrefixName, NamespaceIRI]


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Outcome of `export_to_jsonl`. `skipped` is non-zero only when scoping by
    a selection that contains hashes no longer in the store."""

    exported: int
    skipped: int


def export_to_jsonl(
    s: Session, output_path: Path, *, within: SelectionName | None = None
) -> ExportResult:
    """Export axioms as JSONL with a header line."""
    assert_within_workspace(output_path)

    if not output_path.parent.exists():
        msg = f"Directory '{output_path.parent}' does not exist."
        raise FileNotFoundError(msg)

    selection_size: int | None = None

    if within is not None:
        sel = get_selection(s, within)
        if sel.kind != SelectionKind.AXIOMS:
            raise SelectionKindError(
                name=within,
                expected=SelectionKind.AXIOMS,
                actual=sel.kind,
                operation="export_jsonl",
            )
        selection_size = sel.size
        query = (
            "SELECT json(a.data) FROM axioms a "
            "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
            "ORDER BY a.hash"
        )
        params: tuple[str, ...] = (within,)
    else:
        query = "SELECT json(data) FROM axioms ORDER BY hash"
        params = ()

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
        for (json_text,) in s._conn.execute(query, params):
            f.write(json_text)
            f.write("\n")
            count += 1

    skipped = 0 if selection_size is None else selection_size - count
    return ExportResult(exported=count, skipped=skipped)
