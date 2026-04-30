from ontoloom.ontology import history
from ontoloom.ontology.canonical import truncate_hash
from ontoloom.ontology.connection import Ontology

from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def show_changes(
    path: OntologyPath,
    session: str | None = None,
):
    """Show what changed in the current session (or a specified session).

    Lists all mutation events: adds, deletes, replaces, annotation edits.
    Replace events show old->new hash mapping. Grouped by batch where applicable.
    """
    with Ontology(path) as ont:
        events = history.show_changes(ont, session_id=session)

    if not events:
        return "No changes in this session."

    lines: list[str] = []
    current_batch: str | None = None

    for ev in events:
        if ev.batch_id and ev.batch_id != current_batch:
            current_batch = ev.batch_id
            lines.append(f"\n[batch {truncate_hash(ev.batch_id)}]")
        elif not ev.batch_id and current_batch is not None:
            current_batch = None
            lines.append("")

        h = truncate_hash(ev.axiom_hash)
        match ev.op:
            case "add":
                lines.append(f"  + [{h}] added")
            case "del":
                lines.append(f"  - [{h}] deleted")
            case "replace":
                old = truncate_hash(ev.replaces_hash) if ev.replaces_hash else "?"
                lines.append(f"  ~ [{old}] -> [{h}]")
            case "annotate":
                lines.append(f"  @ [{h}] annotated")
            case _:
                lines.append(f"  ? [{h}] unknown op {ev.op!r}")

    return f"{len(events)} events:\n" + "\n".join(lines)


tool_show_changes = create_tool(show_changes, name="show_changes")
