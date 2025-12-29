from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ontology_hydra.utils.schema import schema_from_model
from ontology_hydra.utils.schema.formatting import format_schema
from ontology_hydra.utils.schema.types import (
    ClassTypeSchema,
    DataType,
    EnumTypeSchema,
    EnumValue,
    ListExpression,
    LiteralExpression,
    OptionalExpression,
    PrimitiveExpression,
    PropertyName,
    PropertySchema,
    RefExpression,
    Schema,
    TypeName,
    UnionExpression,
)

EXAMPLE_SCHEMA = Schema(
    name="ExampleRoot",
    properties={
        PropertyName("id"): PropertySchema(
            type=PrimitiveExpression(dtype=DataType.STRING),
        ),
        PropertyName("status"): PropertySchema(
            type=RefExpression(name=TypeName("Status")),
        ),
        PropertyName("owner"): PropertySchema(
            type=RefExpression(name=TypeName("User")),
        ),
        PropertyName("contributors"): PropertySchema(
            type=OptionalExpression(
                value=ListExpression(items=RefExpression(name=TypeName("User")))
            ),
        ),
        PropertyName("labels"): PropertySchema(
            type=OptionalExpression(
                value=ListExpression(items=PrimitiveExpression(dtype=DataType.STRING))
            ),
        ),
        PropertyName("visibility"): PropertySchema(
            type=RefExpression(name=TypeName("Visibility")),
        ),
        PropertyName("metadata"): PropertySchema(
            type=OptionalExpression(value=RefExpression(name=TypeName("Metadata"))),
        ),
        PropertyName("attachments"): PropertySchema(
            type=ListExpression(items=RefExpression(name=TypeName("Attachment"))),
        ),
    },
    types={
        TypeName("Status"): EnumTypeSchema(
            values=[
                EnumValue("draft"),
                EnumValue("review"),
                EnumValue("published"),
            ],
        ),
        TypeName("Visibility"): EnumTypeSchema(
            values=[
                EnumValue("public"),
                EnumValue("internal"),
                EnumValue("private"),
            ],
        ),
        TypeName("MediaType"): EnumTypeSchema(
            values=[
                EnumValue("text/plain"),
                EnumValue("application/json"),
                EnumValue("image/png"),
            ],
        ),
        TypeName("Role"): EnumTypeSchema(
            values=[
                EnumValue("admin"),
                EnumValue("editor"),
                EnumValue("viewer"),
            ],
        ),
        TypeName("User"): ClassTypeSchema(
            properties={
                PropertyName("user_id"): PropertySchema(
                    type=PrimitiveExpression(dtype=DataType.STRING),
                ),
                PropertyName("email"): PropertySchema(
                    type=PrimitiveExpression(dtype=DataType.STRING),
                ),
                PropertyName("roles"): PropertySchema(
                    type=OptionalExpression(
                        value=ListExpression(items=RefExpression(name=TypeName("Role")))
                    ),
                ),
            },
        ),
        TypeName("Metadata"): ClassTypeSchema(
            properties={
                PropertyName("version"): PropertySchema(
                    type=UnionExpression(
                        any_of=[
                            PrimitiveExpression(dtype=DataType.INT),
                            LiteralExpression(value="v1"),
                            LiteralExpression(value="v2"),
                        ]
                    ),
                ),
                PropertyName("checksum"): PropertySchema(
                    type=OptionalExpression(value=PrimitiveExpression(dtype=DataType.STRING)),
                ),
            },
        ),
        TypeName("Attachment"): ClassTypeSchema(
            properties={
                PropertyName("filename"): PropertySchema(
                    type=PrimitiveExpression(dtype=DataType.STRING),
                ),
                PropertyName("size_bytes"): PropertySchema(
                    type=PrimitiveExpression(dtype=DataType.INT),
                ),
                PropertyName("content"): PropertySchema(
                    type=OptionalExpression(
                        value=UnionExpression(
                            any_of=[
                                PrimitiveExpression(dtype=DataType.STRING),
                                ListExpression(items=PrimitiveExpression(dtype=DataType.INT)),
                            ]
                        )
                    ),
                ),
                PropertyName("media_type"): PropertySchema(
                    type=RefExpression(name=TypeName("MediaType")),
                ),
            },
        ),
    },
)


# Example Pydantic models derived from EXAMPLE_SCHEMA.
class Status(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"


class Visibility(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVATE = "private"


class MediaType(StrEnum):
    TEXT_PLAIN = "text/plain"
    APPLICATION_JSON = "application/json"
    IMAGE_PNG = "image/png"


class Role(StrEnum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class User(BaseModel):
    model_config = ConfigDict(strict=True)

    user_id: str
    email: str
    roles: list[Role] | None = None


class Metadata(BaseModel):
    model_config = ConfigDict(strict=True)

    version: int | Literal["v1", "v2"]
    checksum: str | None = None


class Attachment(BaseModel):
    model_config = ConfigDict(strict=True)

    filename: str
    size_bytes: int
    content: str | list[int] | None = None
    media_type: MediaType


class ExampleRoot(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    status: Status
    owner: User
    contributors: list[User] | None = None
    labels: list[str] | None = None
    visibility: Visibility
    metadata: Metadata | None = None
    attachments: list[Attachment]


print(format_schema(schema_from_model(ExampleRoot)))
print("\n\n\n\nvs\n\n\n\n\n")
print(format_schema(EXAMPLE_SCHEMA))

print(format_schema(EXAMPLE_SCHEMA) == format_schema(schema_from_model(ExampleRoot)))

test_schema = schema_from_model(ExampleRoot)

print(test_schema.model_dump_json(exclude_none=True))
print(EXAMPLE_SCHEMA.model_dump_json(exclude_none=True))
