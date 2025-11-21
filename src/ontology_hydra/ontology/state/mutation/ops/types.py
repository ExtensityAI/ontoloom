from .add_class import AddClassOperation
from .add_data_property import AddDataPropertyOperation
from .add_object_property import AddObjectPropertyOperation
from .remove_class import RemoveClassOperation
from .remove_property import RemovePropertyOperation
from .update_data_property import UpdateDataPropertyOperation
from .update_object_property import UpdateObjectPropertyOperation

Operation = (
    AddClassOperation
    | RemoveClassOperation
    | AddObjectPropertyOperation
    | UpdateObjectPropertyOperation
    | AddDataPropertyOperation
    | UpdateDataPropertyOperation
    | RemovePropertyOperation
)
