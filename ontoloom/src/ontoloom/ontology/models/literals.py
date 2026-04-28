from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


_IRI_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_.-]*)?:[^\x00-\x1f]+$")


class IRI(str):
    """An OWL entity identifier in `prefix:local_name` format.

    Examples:
        IRI(":Dog")        → :Dog
        IRI("owl:Thing")   → owl:Thing
        IRI("xsd:integer") → xsd:integer
    """

    def __new__(cls, value: str):
        if not _IRI_RE.match(value):
            msg = f"IRI must be in 'prefix:local_name' format, got {value!r}"
            raise ValueError(msg)
        return super().__new__(cls, value)

    @property
    def prefix(self) -> str:
        return self.split(":", 1)[0]

    @property
    def local_name(self) -> str:
        return self.split(":", 1)[1]

    def __repr__(self):
        return f"IRI({self})"

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema())

    @classmethod
    def __get_pydantic_json_schema__(cls, schema: Any, handler: Any) -> dict[str, Any]:
        return {
            "type": "string",
            "description": "IRI in `prefix:local_name` format",
            "pattern": r"^([a-zA-Z_][a-zA-Z0-9_.-]*)?:.+$",
            "examples": [":Dog", "owl:Thing", "rdfs:label"],
        }


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

    def __str__(self) -> str:
        return f'"{self.value}"^^{self.datatype.value}'


class LangLiteral(FrozenModel):
    """A value with a language tag: "Dog"@en"""

    value: str
    lang: str = Field(default="en", pattern=r"^$|^[a-zA-Z]{2,3}(-[a-zA-Z0-9]+)*$")

    def __str__(self) -> str:
        return f'"{self.value}"@{self.lang}'


class Annotation(FrozenModel):
    """A property-value pair attached to an axiom. Not a standalone axiom."""

    property: IRI
    value: IRI | TypedLiteral | LangLiteral


# -- Data Range Expressions --


class BaseDataRange(FrozenModel):
    """Base for all data range expressions."""


class DataIntersectionOf(BaseDataRange):
    """Intersection of data ranges."""

    type: Literal["DataIntersectionOf"] = "DataIntersectionOf"
    operands: tuple[DataRange, ...] = Field(..., min_length=2)

    def __str__(self) -> str:
        return " ⊓ ".join(_fmt_data_range(o) for o in self.operands)


class DataOneOf(BaseDataRange):
    """A singleton literal value. OWL 2 EL restricts DataOneOf to exactly one value."""

    type: Literal["DataOneOf"] = "DataOneOf"
    value: TypedLiteral | LangLiteral

    def __str__(self) -> str:
        return f"{{{self.value}}}"


DataRange = (
    DataType
    | Annotated[
        DataIntersectionOf | DataOneOf,
        Field(discriminator="type"),
    ]
)


def _fmt_data_range(dr: DataRange):
    """Format a DataRange union value as a compact string."""
    if isinstance(dr, DataType):
        return dr.value
    return str(dr)


DataIntersectionOf.model_rebuild()
