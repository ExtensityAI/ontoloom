from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, override

from pydantic import Field

from ontoloom.models import FrozenModel, tagged_union_meta
from ontoloom.owl.markers import Unordered


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

    type: Literal["TypedLiteral"] = "TypedLiteral"
    value: str
    datatype: DataType = DataType.STRING

    @override
    def __str__(self) -> str:
        return f'"{self.value}"^^{self.datatype.value}'


class LangLiteral(FrozenModel):
    """A value with a language tag: "Dog"@en"""

    type: Literal["LangLiteral"] = "LangLiteral"
    value: str
    # Empty string is a valid sentinel meaning "no language tag". Prefer an
    # explicit tag (e.g. lang="en") whenever the language is known.
    lang: str = Field(default="en", pattern=r"^$|^[a-zA-Z]{2,3}(-[a-zA-Z0-9]+)*$")

    @override
    def __str__(self) -> str:
        return f'"{self.value}"@{self.lang}'


LiteralValue = Annotated[TypedLiteral | LangLiteral, *tagged_union_meta()]


# -- Data Range Expressions --


class DataTypeRef(FrozenModel):
    """Wraps a `DataType` enum so the `DataRange` union is uniformly tagged.

    Without this wrapper, `DataRange` mixes a bare-string member (`DataType` is a
    `StrEnum`) with discriminated-model members, producing a nested
    `anyOf[oneOf, string]` JSON Schema that LLMs mishandle. See
    `feedback_no_nested_annotated_unions.md`.
    """

    type: Literal["DataTypeRef"] = "DataTypeRef"
    value: DataType

    @override
    def __str__(self) -> str:
        return self.value.value


class DataIntersectionOf(FrozenModel):
    """Intersection of data ranges."""

    type: Literal["DataIntersectionOf"] = "DataIntersectionOf"
    operands: Annotated[
        tuple[DataRange, ...],
        Unordered(),
        Field(min_length=2),
    ]

    @override
    def __str__(self) -> str:
        return " ⊓ ".join(str(o) for o in self.operands)


class DataOneOf(FrozenModel):
    """A singleton literal value. OWL 2 EL restricts DataOneOf to exactly one value."""

    type: Literal["DataOneOf"] = "DataOneOf"
    value: LiteralValue

    @override
    def __str__(self) -> str:
        return f"{{{self.value}}}"


DataRange = Annotated[
    DataTypeRef | DataIntersectionOf | DataOneOf,
    *tagged_union_meta(),
]


DataIntersectionOf.model_rebuild()
