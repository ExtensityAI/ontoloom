from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

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


class DataType(StrEnum):
    """Datatypes permitted in OWL 2 EL."""

    # RDF/RDFS/OWL
    PLAIN_LITERAL = "rdf:PlainLiteral"
    XML_LITERAL = "rdf:XMLLiteral"
    LITERAL = "rdfs:Literal"
    REAL = "owl:real"
    RATIONAL = "owl:rational"

    # XSD numeric
    DECIMAL = "xsd:decimal"
    INTEGER = "xsd:integer"
    NON_NEGATIVE_INTEGER = "xsd:nonNegativeInteger"

    # XSD string
    STRING = "xsd:string"
    NORMALIZED_STRING = "xsd:normalizedString"
    TOKEN = "xsd:token"
    NAME = "xsd:Name"
    NCNAME = "xsd:NCName"
    NMTOKEN = "xsd:NMTOKEN"

    # XSD binary
    HEX_BINARY = "xsd:hexBinary"
    BASE64_BINARY = "xsd:base64Binary"

    # XSD other
    ANY_URI = "xsd:anyURI"
    DATE_TIME = "xsd:dateTime"
    DATE_TIME_STAMP = "xsd:dateTimeStamp"


class TypedLiteral(FrozenModel):
    """A value with a datatype: "42"^^xsd:integer"""

    value: str
    datatype: DataType = DataType.STRING

    def __str__(self):
        return f'"{self.value}"^^{self.datatype.value}'


class LangLiteral(FrozenModel):
    """A value with a language tag: "Dog"@en"""

    value: str
    lang: str = "en"

    def __str__(self) -> str:
        return f'"{self.value}"@{self.lang}'


# -- Data Range Expressions --


class BaseDataRange(FrozenModel):
    """Base for all data range expressions."""


class DataIntersectionOf(BaseDataRange):
    """Intersection of data ranges."""

    type: Literal["DataIntersectionOf"] = "DataIntersectionOf"
    operands: list[DataRange] = Field(..., min_length=2)

    def __str__(self) -> str:
        return " ⊓ ".join(_fmt_data_range(o) for o in self.operands)


class DataOneOf(BaseDataRange):
    """Union of data ranges. Due to us supporting OWL2 EL, only one option is allowed."""

    type: Literal["DataOneOf"] = "DataOneOf"
    value: TypedLiteral

    def __str__(self) -> str:
        return f"{{{self.value}}}"


DataRange = (
    DataType
    | Annotated[
        DataIntersectionOf | DataOneOf,
        Field(discriminator="type"),
    ]
)


def _fmt_data_range(dr: DataRange) -> str:
    """Format a DataRange union value as a compact string."""
    if isinstance(dr, DataType):
        return dr.value
    return str(dr)


DataIntersectionOf.model_rebuild()
