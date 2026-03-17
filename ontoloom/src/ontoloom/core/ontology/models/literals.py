from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field

from ontoloom.core.ontology.models.base import FrozenModel


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


class LangLiteral(FrozenModel):
    """A value with a language tag: "Dog"@en"""

    value: str
    lang: str = "en"


# -- Data Range Expressions --


class BaseDataRange(FrozenModel):
    """Base for all data range expressions."""


class DataIntersectionOf(BaseDataRange):
    """Intersection of data ranges."""

    type: Literal["DataIntersectionOf"] = "DataIntersectionOf"
    operands: list[DataRange] = Field(..., min_length=2)


class DataOneOf(BaseDataRange):
    """Union of data ranges. Due to us supporting OWL2 EL, only one option is allowed."""

    type: Literal["DataOneOf"] = "DataOneOf"
    value: TypedLiteral


DataRange = (
    DataType
    | Annotated[
        DataIntersectionOf | DataOneOf,
        Field(discriminator="type"),
    ]
)

DataIntersectionOf.model_rebuild()
