"""Wire-form selection-ref aliases for MCP tool parameters.

The narrow TypedStrs (`EntitySelectionName`, `AxiomSelectionName` in core;
`Locked*SelectionName` in `locking`) carry their own regex and json-schema
metadata via `TypedStr.__get_pydantic_*_schema__`, so the unions need no
extra validator wiring.
"""

from ontoloom.selections.types import SelectionRef

from ontoloom_mcp.components.locking import LockedSelectionRef

type SelectionRefParam = SelectionRef
type LockedSelectionRefParam = LockedSelectionRef
