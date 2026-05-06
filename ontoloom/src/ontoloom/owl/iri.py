import re
from typing import override

from ontoloom.models import TypedStr

IRI_PATTERN = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_.-]*)?:[^\x00-\x1f]+$")


class IRI(TypedStr):
    """An OWL entity identifier in `prefix:local_name` format.

    Examples:
        IRI(":Dog")        -> :Dog
        IRI("owl:Thing")   -> owl:Thing
        IRI("xsd:integer") -> xsd:integer
    """

    description = "IRI in `prefix:local_name` format"
    pattern = r"^([a-zA-Z_][a-zA-Z0-9_.-]*)?:.+$"
    examples = (":Dog", "owl:Thing", "rdfs:label")

    @override
    @classmethod
    def parse(cls, value: str):
        if not IRI_PATTERN.match(value):
            msg = f"IRI must be in 'prefix:local_name' format, got {value!r}"
            raise ValueError(msg)
        return value

    @property
    def prefix(self):
        return self.split(":", 1)[0]

    @property
    def local_name(self):
        return self.split(":", 1)[1]
