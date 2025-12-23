from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ontology_hydra.utils.schema import (
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
    format_schema,
    schema_from_model,
)

EXAMPLE_SCHEMA = Schema(
    description="Example schema exercising ref, union, list, primitive, and literal types.",
    properties={
        PropertyName("id"): PropertySchema(
            description="Stable document identifier.",
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
            description="Workflow state for a document.",
            values=[
                EnumValue("draft"),
                EnumValue("review"),
                EnumValue("published"),
            ],
        ),
        TypeName("Visibility"): EnumTypeSchema(
            description="Access level for the document.",
            values=[
                EnumValue("public"),
                EnumValue("internal"),
                EnumValue("private"),
            ],
        ),
        TypeName("MediaType"): EnumTypeSchema(
            description="MIME types supported for attachments.",
            values=[
                EnumValue("text/plain"),
                EnumValue("application/json"),
                EnumValue("image/png"),
            ],
        ),
        TypeName("Role"): EnumTypeSchema(
            description="Account role used for access control.",
            values=[
                EnumValue("admin"),
                EnumValue("editor"),
                EnumValue("viewer"),
            ],
        ),
        TypeName("User"): ClassTypeSchema(
            description="Account holder with role assignments.",
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
            description="Structured metadata with mixed literals and primitives.",
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
            description="Binary or textual attachments for a document.",
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


class UserModel(BaseModel):
    model_config = ConfigDict(strict=True)

    user_id: str
    email: str
    roles: list[Role] | None = None


class MetadataModel(BaseModel):
    model_config = ConfigDict(strict=True)

    version: int | Literal["v1", "v2"]
    checksum: str | None = None


class AttachmentModel(BaseModel):
    model_config = ConfigDict(strict=True)

    filename: str
    size_bytes: int
    content: str | list[int] | None = None
    media_type: MediaType


class ExampleRootModel(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    status: Status
    owner: UserModel
    contributors: list[UserModel] | None = None
    labels: list[str] | None = None
    visibility: Visibility
    metadata: MetadataModel | None = None
    attachments: list[AttachmentModel]


print("\n\n\n\nvs\n\n\n\n\n")
print(format_schema(EXAMPLE_SCHEMA))

test_schema = schema_from_model(ExampleRootModel)

print(test_schema.model_dump_json(exclude_none=True))
print(EXAMPLE_SCHEMA.model_dump_json(exclude_none=True))
