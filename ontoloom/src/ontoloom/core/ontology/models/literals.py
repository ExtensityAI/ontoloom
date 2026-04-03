from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


class FrozenModel(BaseModel):
    """Base for all OWL 2 EL model classes. Immutable by default."""

    model_config = ConfigDict(frozen=True)


class IRI(str):
    """An OWL entity identifier in `prefix:local_name` format.

    Examples:
        IRI(":Dog")        → :Dog
        IRI("owl:Thing")   → owl:Thing
        IRI("xsd:integer") → xsd:integer
    """

    # If prefix/local_name splitting becomes a bottleneck, cache the split result.

    def __new__(cls, value: str):
        parts = value.split(":", 1)
        if len(parts) != 2 or not parts[1]:
            msg = f"IRI must be in 'prefix:local_name' format, got '{value}'"
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
            "pattern": r"^[^:]*:.+$",
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
    lang: str = "en"

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
    operands: list[DataRange] = Field(..., min_length=2)

    def __str__(self) -> str:
        return " ⊓ ".join(_fmt_data_range(o) for o in self.operands)


class DataOneOf(BaseDataRange):
    """Union of data ranges. Due to us supporting OWL2 EL, only one option is allowed."""

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


def _fmt_data_range(dr: DataRange) -> str:
    """Format a DataRange union value as a compact string."""
    if isinstance(dr, DataType):
        return dr.value
    return str(dr)


DataIntersectionOf.model_rebuild()
