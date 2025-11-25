from ontology_hydra.ontology.state.ops.update_class import UpdateClassOperationArgs

from .add_class import AddClassOperationArgs
from .add_data_property import AddDataPropertyOperationArgs
from .add_object_property import AddObjectPropertyOperationArgs
from .del_class import DeleteClassOperationArgs
from .del_property import DeletePropertyOperationArgs
from .update_data_property import UpdateDataPropertyOperationArgs
from .update_object_property import UpdateObjectPropertyOperationArgs

OperationArgs = (
    AddClassOperationArgs
    | UpdateClassOperationArgs
    | DeleteClassOperationArgs
    | AddObjectPropertyOperationArgs
    | UpdateObjectPropertyOperationArgs
    | AddDataPropertyOperationArgs
    | UpdateDataPropertyOperationArgs
    | DeletePropertyOperationArgs
)
