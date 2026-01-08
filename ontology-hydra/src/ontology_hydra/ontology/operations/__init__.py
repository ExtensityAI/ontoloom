from ontology_hydra.ontology.operations.add_class import AddClassOperation
from ontology_hydra.ontology.operations.add_data_property import AddDataPropertyOperation
from ontology_hydra.ontology.operations.add_object_property import AddObjectPropertyOperation
from ontology_hydra.ontology.operations.delete_class import DeleteClassOperation
from ontology_hydra.ontology.operations.delete_data_property import DeleteDataPropertyOperation
from ontology_hydra.ontology.operations.delete_object_property import DeleteObjectPropertyOperation
from ontology_hydra.ontology.operations.merge_classes import MergeClassesOperation
from ontology_hydra.ontology.operations.update_class import UpdateClassOperation
from ontology_hydra.ontology.operations.update_data_property import UpdateDataPropertyOperation
from ontology_hydra.ontology.operations.update_object_property import UpdateObjectPropertyOperation

from .ops import Operation

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
