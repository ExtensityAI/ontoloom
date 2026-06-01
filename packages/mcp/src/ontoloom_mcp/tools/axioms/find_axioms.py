from typing import Annotated

from annotated_types import MinLen
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.owl.iri import IRI
from ontoloom.query.constraints import (
    AnnotationTextMatches,
    AxiomConstraint,
    HasAnyAnnotation,
)
from ontoloom.query.dispatch import execute, resolve_within
from ontoloom.query.find_axioms import FindAxioms
from ontoloom.selections.store import upsert_axiom_selection
from ontoloom.selections.types import SelectionName, WriteMode

from ontoloom_mcp.components.formatting import (
    FindAxiomsSource,
    fetch_preview_data,
    format_selection_write,
    format_source,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def find_axioms(
    path: OntologyPath,
    into: SelectionName,
    mode: WriteMode = WriteMode.CREATE,
    query: Annotated[str, MinLen(1)] | None = None,
    properties: Annotated[list[IRI], MinLen(1)] | None = None,
    within: SelectionName | None = None,
):
    """Find axioms by axiom-level annotation text or property; save matches to a selection.

    Use `read_selection` to paginate the saved selection; combine with `match_axioms`
    via `within=` to narrow by structural shape.

    Args:
    - `into`: Name for the output selection (e.g. `"todos"`).
    - `mode`: `create` (default) refuses if the selection name already exists; `replace` overwrites it.
    - `query`: Case-insensitive match on axiom-level annotation values. Exact matches
      rank before substring matches.
    - `properties`: Annotation property IRIs. With query, restricts text search to
      these properties; without query, finds axioms with any annotation whose
      property is in the set.
    - `within`: Restrict search to a named selection.
    """
    if query is None and properties is None:
        msg = "find_axioms requires at least one of `query` or `properties`."
        raise ToolError(msg)

    props_tuple = tuple(properties or ())
    src = FindAxiomsSource(query=query, properties=props_tuple, within=within)

    ont = Ontology(path)
    with session(ont) as s:
        scope: tuple[AxiomConstraint, ...] = (
            (resolve_within(s, within),) if within is not None else ()
        )

        if query is not None:
            text: tuple[AxiomConstraint, ...] = (
                AnnotationTextMatches(query=query, properties=props_tuple),
            )
        else:
            text = (HasAnyAnnotation(properties=props_tuple),)

        hashes = execute(s, FindAxioms(constraints=(*text, *scope)))

        upserted = upsert_axiom_selection(s, into, hashes, format_source(src), mode=mode)
        preview = fetch_preview_data(s, upserted)
        s.commit()

    return format_selection_write(upserted, preview, src)


tool_find_axioms = create_tool(
    find_axioms,
    name="find_axioms",
    annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True),
)
