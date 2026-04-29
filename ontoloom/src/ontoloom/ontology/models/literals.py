from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ontoloom.ontology.models.markers import EntityKind, EntityPosition, Unordered


class EntityType(StrEnum):
    """The kind of OWL entity an IRI refers to."""

    CLASS = "Class"
    OBJECT_PROPERTY = "ObjectProperty"
    DATA_PROPERTY = "DataProperty"
    ANNOTATION_PROPERTY = "AnnotationProperty"
    NAMED_INDIVIDUAL = "NamedIndividual"
    DATATYPE = "Datatype"


class Position(StrEnum):
    """Structural role an entity plays within an axiom.

    18 values: 17 stored in axiom_entities.position + ANY (query-time only).
    """

    # Query-time only (never stored in DB)
    ANY = "any"

    # SubClassOf — named superclass
    SUB_CLASS = "sub_class"
    SUPER_CLASS = "super_class"

    # Class expression restrictions (ObjectSomeValuesFrom, ObjectHasValue, etc.)
    RESTRICTION_PROPERTY = "restriction_property"
    FILLER = "filler"

    # Sub*PropertyOf
    SUB_PROPERTY = "sub_property"
    SUPER_PROPERTY = "super_property"

    # SubObjectPropertyOfChain
    CHAIN_MEMBER = "chain_member"

    # AnnotationAssertion
    SUBJECT = "subject"
    PROPERTY = "property"
    VALUE = "value"

    # *Domain / *Range
    DOMAIN = "domain"
    RANGE = "range"

    # ObjectPropertyAssertion
    SOURCE = "source"
    TARGET = "target"

    # ClassAssertion
    INDIVIDUAL = "individual"
    CLASS = "class"

    # EquivalentClasses, DisjointClasses, SameIndividual, DifferentIndividuals
    MEMBER = "member"

    # Declaration
    ENTITY = "entity"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TaggedModel(FrozenModel):
    """A FrozenModel that participates in a discriminated union via a `type` field.

    Subclasses must declare `type: Literal["..."] = "..."`. Intermediate bases
    that don't declare their own `type` are skipped silently. The literal default
    is mirrored to a `type_` ClassVar for class-level access (e.g. SQL queries).
    """

    type_: ClassVar[str] = ""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        if "type" not in cls.__annotations__:
            return
        default = cls.model_fields["type"].default
        if not isinstance(default, str) or not default:
            msg = f'{cls.__name__}.type must be Literal["..."] = "..." with a non-empty str default'
            raise TypeError(msg)
        cls.type_ = default


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

    property: Annotated[
        IRI,
        EntityKind(EntityType.ANNOTATION_PROPERTY),
        EntityPosition(Position.PROPERTY),
    ]
    value: Annotated[
        IRI | TypedLiteral | LangLiteral,
        EntityPosition(Position.VALUE),
    ]


# -- Data Range Expressions --


class BaseDataRange(TaggedModel):
    """Base for all data range expressions."""


class DataIntersectionOf(BaseDataRange):
    """Intersection of data ranges."""

    type: Literal["DataIntersectionOf"] = "DataIntersectionOf"
    operands: Annotated[
        tuple[DataRange, ...],
        Unordered(),
        Field(min_length=2),
    ]

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
