from typing import Annotated

from pydantic import AfterValidator, Field


def _validate_iri(v: str):
    if ":" not in v:
        msg = f"IRI must be in 'prefix:local_name' format, got '{v}'"
        raise ValueError(msg)

    parts = v.split(":")

    if len(parts) != 2:
        msg = f"IRI must be in 'prefix:local_name' format, got '{v}'"
        raise ValueError(msg)

    _, local = parts

    if not local:
        msg = f"IRI missing local name after ':', got '{v}'"
        raise ValueError(msg)

    return v


StrIRI = Annotated[
    str,
    Field(description="IRI in 'prefix:local_name' format", examples=[":Car", "owl:Thing"]),
    AfterValidator(_validate_iri),
]

ClassIRI = Annotated[
    StrIRI,
    Field(description="IRI of an OWL class", examples=[":Dog", ":Animal", "owl:Thing"]),
]
ObjectPropertyIRI = Annotated[
    StrIRI,
    Field(description="IRI of an object property", examples=[":hasPart", ":hasParent"]),
]
DataPropertyIRI = Annotated[
    StrIRI,
    Field(description="IRI of a data property", examples=[":hasAge", ":hasName"]),
]
IndividualIRI = Annotated[
    StrIRI,
    Field(description="IRI of a named individual", examples=[":Alice", ":Bob"]),
]
AnnotationPropertyIRI = Annotated[
    StrIRI,
    Field(description="IRI of an annotation property", examples=["rdfs:label", "rdfs:comment"]),
]
