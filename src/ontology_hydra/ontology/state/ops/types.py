from ontology_hydra.ontology.state.ops.update_class import UpdateClassOperation

from .add_class import AddClassOperation
from .add_data_property import AddDataPropertyOperation
from .add_object_property import AddObjectPropertyOperation
from .del_class import DeleteClassOperation
from .del_property import DeletePropertyOperation
from .update_data_property import UpdateDataPropertyOperation
from .update_object_property import UpdateObjectPropertyOperation

Operation = (
    AddClassOperation
    | UpdateClassOperation
    | DeleteClassOperation
    | AddObjectPropertyOperation
    | UpdateObjectPropertyOperation
    | AddDataPropertyOperation
    | UpdateDataPropertyOperation
    | DeletePropertyOperation
)
