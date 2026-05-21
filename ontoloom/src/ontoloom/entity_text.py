"""Schema vocabulary for the `entity_text` SQL table.

Hosting these names here keeps axiom writers and readers from reaching
into each other and breaks what would otherwise be a near-circular
dependency.
"""

# Sentinel for `entity_text.property` rows that index an IRI's local-name
# (vs. real annotation-property values).
LOCAL_NAME_PROPERTY = "local_name"

# Compact form of `owl:deprecated`. The codebase stores IRIs as CURIEs
# throughout, so this is the only form seen by the `entity_text.property` column.
OWL_DEPRECATED_PROPERTY = "owl:deprecated"
