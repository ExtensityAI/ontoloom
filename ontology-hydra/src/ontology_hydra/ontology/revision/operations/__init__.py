from .add_class import AddClassOperation
from .add_data_property import AddDataPropertyOperation
from .add_object_property import AddObjectPropertyOperation
from .delete_class import DeleteClassOperation
from .delete_data_property import DeleteDataPropertyOperation
from .delete_object_property import DeleteObjectPropertyOperation
from .merge_classes import MergeClassesOperation
from .ops import Operation
from .update_class import UpdateClassOperation
from .update_data_property import UpdateDataPropertyOperation
from .update_object_property import UpdateObjectPropertyOperation

__all__ = [
    "AddClassOperation",
    "AddDataPropertyOperation",
    "AddObjectPropertyOperation",
    "DeleteClassOperation",
    "DeleteDataPropertyOperation",
    "DeleteObjectPropertyOperation",
    "MergeClassesOperation",
    "Operation",
    "UpdateClassOperation",
    "UpdateDataPropertyOperation",
    "UpdateObjectPropertyOperation",
]
