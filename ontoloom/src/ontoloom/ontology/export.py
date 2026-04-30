from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from ontoloom.ontology import prefixes as prefixes_module
from ontoloom.ontology import selections
from ontoloom.ontology.connection import (
    CURRENT_SCHEMA_VERSION,
    Ontology,
    assert_within_workspace,
)
from ontoloom.ontology.errors import BadRequestError, SelectionKindError
from ontoloom.ontology.load import load_axiom
from ontoloom.ontology.models.axioms import Axiom
from ontoloom.ontology.types import SelectionKind

FORMAT_VERSION = 1


class HeaderRecord(BaseModel, frozen=True):
    format: Literal["ontoloom-jsonl"]
    format_version: int
    schema_version: int
    exported_at: str
    prefixes: dict[str, str]


@dataclass(frozen=True, slots=True)
class ImportJsonlResult:
    header: HeaderRecord
    axioms: list[Axiom]


def to_jsonl(ont: Ontology, output_path: Path, *, within: str | None = None) -> int:
    """Export axioms as JSONL with a header line. Returns count of exported axioms."""
    assert_within_workspace(output_path)
    # A global: we need more space, like empty lines and all. else, this is crammed and hard to understand. usual heuristic is a space before an if or else or try or for, but NOT if it is preceded by another if or else or try or for, you know what I mean? make this a general principle maybe! also, usually if an if or for or else block is long and there is more code after, then also add an empty line. VERY IMPORTANT, should be in your global python memory.
    if within is not None:
        sel = selections.get(ont, within)
        if sel.kind != SelectionKind.AXIOMS:
            raise SelectionKindError(
                name=within,
                expected=SelectionKind.AXIOMS,
                actual=sel.kind,
                operation="export_jsonl",
            )
        query = (
            "SELECT json(a.data) FROM axioms a "
            "JOIN selection_items si ON si.item = a.hash AND si.selection_name = ? "
            "ORDER BY a.hash"
        )
        params: tuple[str, ...] = (within,)
    else:
        query = "SELECT json(data) FROM axioms ORDER BY hash"
        params = ()

    if not output_path.parent.exists():
        # A: should check this in the beginning. maybe make this an expect or validate function - like validate_directory_exists or ensure or sth?
        msg = f"Directory '{output_path.parent}' does not exist."
        raise BadRequestError(msg)

    header = HeaderRecord(
        format="ontoloom-jsonl",
        format_version=FORMAT_VERSION,
        schema_version=CURRENT_SCHEMA_VERSION,
        exported_at=datetime.now(UTC).isoformat(),
        prefixes=prefixes_module.list_all(ont),
    )

    count = 0
    with output_path.open("w") as f:
        f.write(header.model_dump_json())
        f.write("\n")
        for (json_text,) in ont.conn.execute(query, params):
            f.write(json_text)
            f.write("\n")
            count += 1
    return count


def import_jsonl(path: Path) -> ImportJsonlResult:
    """Read a JSONL export. Validates the header and parses all axiom lines."""
    assert_within_workspace(path)
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    if not lines:
        msg = f"'{path}' is empty"
        raise ValueError(msg)
    header = HeaderRecord.model_validate_json(lines[0])
    if header.format_version > FORMAT_VERSION:
        msg = f"Unsupported format_version {header.format_version} (this build supports up to {FORMAT_VERSION})"
        raise ValueError(msg)
    axioms_list = [load_axiom(line) for line in lines[1:]]
    return ImportJsonlResult(header=header, axioms=axioms_list)
