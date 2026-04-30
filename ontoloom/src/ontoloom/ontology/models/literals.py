from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Any, Literal, override

from pydantic import Field

from ontoloom.ontology.models._pydantic import FrozenModel, TaggedModel, _PydanticStr
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


# Subset of Position values that may appear in an EntityPosition marker or be
# persisted to axiom_entities.position. ANY is reserved for query-time filters.
type StoredPosition = Literal[
    Position.SUB_CLASS,
    Position.SUPER_CLASS,
    Position.RESTRICTION_PROPERTY,
    Position.FILLER,
    Position.SUB_PROPERTY,
    Position.SUPER_PROPERTY,
    Position.CHAIN_MEMBER,
    Position.SUBJECT,
    Position.PROPERTY,
    Position.VALUE,
    Position.DOMAIN,
    Position.RANGE,
    Position.SOURCE,
    Position.TARGET,
    Position.INDIVIDUAL,
    Position.CLASS,
    Position.MEMBER,
    Position.ENTITY,
]


IRI_PATTERN = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_.-]*)?:[^\x00-\x1f]+$")


class IRI(_PydanticStr):
    """An OWL entity identifier in `prefix:local_name` format.

    Examples:
        IRI(":Dog")        -> :Dog
        IRI("owl:Thing")   -> owl:Thing
        IRI("xsd:integer") -> xsd:integer
    """

    def __new__(cls, value: str):
        if not IRI_PATTERN.match(value):
            msg = f"IRI must be in 'prefix:local_name' format, got {value!r}"
            raise ValueError(msg)
        return super().__new__(cls, value)

    @property
    def prefix(self) -> str:
        return self.split(":", 1)[0]

    @property
    def local_name(self) -> str:
        return self.split(":", 1)[1]

    @override
    def __repr__(self):
        return f"IRI({self})"

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

    @override
    def __str__(self) -> str:
        return f'"{self.value}"^^{self.datatype.value}'


class LangLiteral(FrozenModel):
    """A value with a language tag: "Dog"@en"""

    value: str
    # Empty string is a valid sentinel meaning "no language tag". Prefer an
    # explicit tag (e.g. lang="en") whenever the language is known.
    lang: str = Field(default="en", pattern=r"^$|^[a-zA-Z]{2,3}(-[a-zA-Z0-9]+)*$")

    @override
    def __str__(self) -> str:
        return f'"{self.value}"@{self.lang}'


class Annotation(FrozenModel):
    """A property-value pair attached to an axiom. Not a standalone axiom."""

    property: Annotated[
        IRI,
        EntityKind(EntityType.ANNOTATION_PROPERTY),
        EntityPosition(Position.PROPERTY),
    ]
    # Smart-union by structural disambiguation: IRI is a str subclass,
    # TypedLiteral has `datatype`, LangLiteral has `lang` — all uniquely
    # identifiable without a `type` discriminator field.
    value: Annotated[
        IRI | TypedLiteral | LangLiteral,
        EntityPosition(Position.VALUE),
    ]


# -- Data Range Expressions --


class BaseDataRange(TaggedModel):
    """Base for all data range expressions."""


class DataTypeRef(BaseDataRange):
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


class DataIntersectionOf(BaseDataRange):
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


class DataOneOf(BaseDataRange):
    """A singleton literal value. OWL 2 EL restricts DataOneOf to exactly one value."""

    type: Literal["DataOneOf"] = "DataOneOf"
    value: TypedLiteral | LangLiteral

    @override
    def __str__(self) -> str:
        return f"{{{self.value}}}"


DataRange = Annotated[
    DataTypeRef | DataIntersectionOf | DataOneOf,
    Field(discriminator="type"),
]


DataIntersectionOf.model_rebuild()
