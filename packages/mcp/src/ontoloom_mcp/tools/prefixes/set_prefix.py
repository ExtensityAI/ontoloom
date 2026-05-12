from mcp.types import ToolAnnotations
from ontoloom.connection import Ontology, session
from ontoloom.prefixes import NamespaceIRI, PrefixName
from ontoloom.prefixes import set_prefix as core_set_prefix

from ontoloom_mcp.components.confirmation import (
    ConfirmationRequiredError,
    confirmation_token,
)
from ontoloom_mcp.components.tool import create_tool
from ontoloom_mcp.components.types import OntologyPath


def set_prefix(
    path: OntologyPath,
    name: PrefixName,
    iri: NamespaceIRI,
    confirm: str | None = None,
):
    """Add or update a prefix mapping (e.g. name="ex", iri="http://example.org/").

    Prefixes expand the `prefix:local_name` shorthand used in entity IRIs (e.g.
    `ex:Dog` -> `http://example.org/Dog`).

    Reassigning an in-use prefix changes the meaning of every entity using it.
    The first call raises `ConfirmationRequiredError` with a token; pass that
    token as `confirm=` to apply the change.
    """
    ont = Ontology(path)
    with session(ont) as s:
        result = core_set_prefix(s, name, iri)

        if result.in_use_count > 0 and result.previous_iri is not None:
            token = confirmation_token(
                "set_prefix",
                name,
                iri,
                result.previous_iri,
                str(result.in_use_count),
            )
            if confirm != token:
                msg = (
                    f"Reassigning prefix {str(name)!r} from {str(result.previous_iri)!r} "
                    f"to {str(iri)!r} would change the meaning of "
                    f"{result.in_use_count} entities."
                )
                raise ConfirmationRequiredError(msg, token)

        s.commit()

    if result.previous_iri is None:
        return f"Set prefix `{name}:` -> `{iri}`"

    if result.previous_iri == iri:
        return f"Set prefix `{name}:` -> `{iri}` (unchanged)"

    suffix = f"; {result.in_use_count} entities affected" if result.in_use_count > 0 else ""
    return f"Set prefix `{name}:` -> `{iri}` (was `{result.previous_iri}`{suffix})"


tool_set_prefix = create_tool(
    set_prefix, name="set_prefix", annotations=ToolAnnotations(idempotentHint=True)
)
