from pathlib import Path

from ontoloom.ontology import selections
from ontoloom.ontology.connection import Ontology
from ontoloom.ontology.errors import SelectionKindError
from ontoloom.ontology.types import SelectionKind


def to_jsonl(ont: Ontology, output_path: Path, *, within: str | None = None) -> int:
    """Export axioms as JSONL. Returns count of exported axioms."""
    if within is not None:
        sel = selections.get_info(ont, within)
        if sel.kind != SelectionKind.AXIOMS:
            raise SelectionKindError(
                name=within, expected="axioms", actual=sel.kind, operation="export_jsonl"
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
        msg = f"Directory '{output_path.parent}' does not exist."
        raise ValueError(msg)

    count = 0
    with output_path.open("w") as f:
        for (json_text,) in ont.conn.execute(query, params):
            f.write(json_text)
            f.write("\n")
            count += 1
    return count
