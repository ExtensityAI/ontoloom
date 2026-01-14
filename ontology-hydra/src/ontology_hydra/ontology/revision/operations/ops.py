from typing import Annotated

from pydantic import Field

from .add_class import AddClassOperation
from .add_data_property import AddDataPropertyOperation
from .add_object_property import AddObjectPropertyOperation
from .delete_class import DeleteClassOperation
from .delete_data_property import DeleteDataPropertyOperation
from .delete_object_property import DeleteObjectPropertyOperation
from .merge_classes import MergeClassesOperation
from .update_class import UpdateClassOperation
from .update_data_property import UpdateDataPropertyOperation
from .update_object_property import (
    UpdateObjectPropertyOperation,
)

Operation = Annotated[
    AddClassOperation
    | AddDataPropertyOperation
    | AddObjectPropertyOperation
    | UpdateClassOperation
    | UpdateDataPropertyOperation
    | UpdateObjectPropertyOperation
    | DeleteClassOperation
    | DeleteDataPropertyOperation
    | DeleteObjectPropertyOperation
    | MergeClassesOperation,
    Field(discriminator="op"),
]
