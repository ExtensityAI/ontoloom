from typing import NewType

from pydantic import Field

from ontoloom.core.ontology.models.base import FrozenModel


class IRI(FrozenModel):
    """An OWL entity identifier: prefix + local_name.

    Examples:
        IRI(prefix="", local_name="Dog")        → :Dog
        IRI(prefix="owl", local_name="Thing")    → owl:Thing
        IRI(prefix="xsd", local_name="integer")  → xsd:integer
    """

    prefix: str = Field(default="", description="Namespace prefix ('' for default)")
    local_name: str = Field(..., min_length=1, description="Local name within namespace")

    def __str__(self):
        return f"{self.prefix}:{self.local_name}"

    def __repr__(self):
        return f"IRI({self})"


ClassIRI = NewType("ClassIRI", IRI)
ObjectPropertyIRI = NewType("ObjectPropertyIRI", IRI)
DataPropertyIRI = NewType("DataPropertyIRI", IRI)
IndividualIRI = NewType("IndividualIRI", IRI)
AnnotationPropertyIRI = NewType("AnnotationPropertyIRI", IRI)
