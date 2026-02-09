# TODO: in the beginning, we simply execute operations sequentially. If one fails, we immediately
# raise an error. LATER, we might want to build some execution graph with dependencies, which would
# immediately show that, f.e. an update and a delete operation of the same class are invalid, and we
# can see which operations are actually erroneous (node does not exist), and which operations are
# just blocked (e.g. adding a domain class to a property after the class was created, but creation
# args are wrong so create failed. In this case, adding the domain class is not in itself an error.)
# In this way, we could propagate more errors immediately, likely speeding up execution (and
# precision?)

# TODO: for property updates: assuming a new class is added to domain/range, should we check if the
# class is already part of the domain/range and should we make this an error? if no, maybe a
# warning? not sure

"""Executor for ontology revision operations using pattern matching."""

from ontology_hydra.ontology.models import (
    Class,
    ClassName,
    DataProperty,
    ObjectProperty,
    Ontology,
)
from ontology_hydra.ontology.revision.helpers import (
    get_classes_in_expressions,
    has_cycle,
    remove_class_from_expressions,
    replace_class_refs,
    validate_classes_exist,
)
from ontology_hydra.ontology.revision.operations import (
    AddClass,
    AddDataProperty,
    AddObjectProperty,
    DeleteClass,
    DeleteDataProperty,
    DeleteObjectProperty,
    MergeClasses,
    Operation,
    UpdateClass,
    UpdateDataProperty,
    UpdateObjectProperty,
)


class OperationFailedError(Exception):
    """Raised when executing an operation fails. Includes index and operation context."""

    def __init__(self, index: int, operation: Operation, cause: Exception):
        super().__init__(str(cause))
        self.index = index
        self.operation = operation
        self.__cause__ = cause

def _add_class(op: AddClass, ontology: Ontology) -> Ontology:
    """Add a new class to the ontology."""
    if op.name in ontology.classes:
        msg = f"Class '{op.name}' already exists"
        raise ValueError(msg)

    for parent in op.sub_class_of:
        if parent not in ontology.classes:
            msg = f"Parent class '{parent}' does not exist"
            raise ValueError(msg)

    ontology.classes[op.name] = Class(
        name=op.name,
        description=op.description,
        sub_class_of=op.sub_class_of,
    )

    if has_cycle(ontology, op.name):
        del ontology.classes[op.name]
        msg = f"Adding class '{op.name}' creates a cycle in the hierarchy"
        raise ValueError(msg)

    return ontology


def _update_class(op: UpdateClass, ontology: Ontology) -> Ontology:
    """Update an existing class in the ontology."""
    if op.name not in ontology.classes:
        msg = f"Class '{op.name}' does not exist"
        raise KeyError(msg)

    cls = ontology.classes[op.name]
    old_sub_class_of = cls.sub_class_of

    if op.description is not None:
        cls.description = op.description

    if op.sub_class_of is not None:
        for parent in op.sub_class_of:
            if parent not in ontology.classes:
                msg = f"Parent class '{parent}' does not exist"
                raise ValueError(msg)
        cls.sub_class_of = op.sub_class_of

        if has_cycle(ontology, op.name):
            cls.sub_class_of = old_sub_class_of
            msg = f"Updating class '{op.name}' creates a cycle in the hierarchy"
            raise ValueError(msg)

    if op.new_name is not None and op.new_name != op.name:
        if op.new_name in ontology.classes:
            msg = f"Cannot rename: class '{op.new_name}' already exists"
            raise ValueError(msg)

        del ontology.classes[op.name]
        cls.name = op.new_name
        ontology.classes[op.new_name] = cls
        replace_class_refs(ontology, op.name, op.new_name)

    return ontology


def _delete_class(op: DeleteClass, ontology: Ontology) -> Ontology:
    """Delete a class from the ontology."""
    if op.name not in ontology.classes:
        msg = f"Class '{op.name}' does not exist"
        raise KeyError(msg)

    # check if deletion would leave any data property with empty domain
    for prop_name, prop in ontology.data_properties.items():
        if remove_class_from_expressions(prop.domain, op.name) is None:
            msg = f"Cannot delete class '{op.name}': would leave data property '{prop_name}' with empty domain"
            raise ValueError(msg)

    # check if deletion would leave any object property with empty domain or range
    for prop_name, prop in ontology.object_properties.items():
        if remove_class_from_expressions(prop.domain, op.name) is None:
            msg = f"Cannot delete class '{op.name}': would leave object property '{prop_name}' with empty domain"
            raise ValueError(msg)
        if remove_class_from_expressions(prop.range, op.name) is None:
            msg = f"Cannot delete class '{op.name}': would leave object property '{prop_name}' with empty range"
            raise ValueError(msg)

    # check if deletion would leave any class with no parents
    for cls_name, cls in ontology.classes.items():
        if cls_name != op.name and cls.sub_class_of and cls.sub_class_of == [op.name]:
            msg = f"Cannot delete class '{op.name}': would leave class '{cls_name}' with no parents"
            raise ValueError(msg)

    del ontology.classes[op.name]
    return ontology


def _merge_classes(op: MergeClasses, ontology: Ontology) -> Ontology:
    """Merge multiple classes into a single target class."""
    for source in op.source_classes:
        if source not in ontology.classes:
            msg = f"Source class '{source}' does not exist"
            raise KeyError(msg)

    # Collect all superclasses from source classes
    all_superclasses = set[ClassName]()
    for source in op.source_classes:
        all_superclasses.update(ontology.classes[source].sub_class_of)

    # Remove source classes from superclasses (avoid self-reference)
    all_superclasses -= set(op.source_classes)
    if op.target_name in all_superclasses:
        all_superclasses.remove(op.target_name)

    # Delete source classes
    for source in op.source_classes:
        del ontology.classes[source]

    # Create or update target class
    ontology.classes[op.target_name] = Class(
        name=op.target_name,
        description=op.description,
        sub_class_of=list(all_superclasses),
    )

    # Update all references from source classes to target
    for source in op.source_classes:
        replace_class_refs(ontology, source, op.target_name)

    # Check for cycles after merge
    if has_cycle(ontology, op.target_name):
        # TODO: add more metadata - what creates the cycle?
        msg = f"Merging into '{op.target_name}' creates a cycle in the hierarchy"
        raise ValueError(msg)

    return ontology


def _add_data_property(op: AddDataProperty, ontology: Ontology) -> Ontology:
    """Add a new data property to the ontology."""
    if op.name in ontology.data_properties:
        msg = f"Data property '{op.name}' already exists"
        raise ValueError(msg)

    validate_classes_exist(ontology, get_classes_in_expressions(op.domain), "Domain")

    ontology.data_properties[op.name] = DataProperty(
        name=op.name,
        description=op.description,
        domain=op.domain,
        range=op.range,
    )
    return ontology


def _update_data_property(op: UpdateDataProperty, ontology: Ontology) -> Ontology:
    """Update an existing data property."""
    if op.name not in ontology.data_properties:
        msg = f"Data property '{op.name}' does not exist"
        raise KeyError(msg)

    prop = ontology.data_properties[op.name]

    if op.description is not None:
        prop.description = op.description

    if op.domain is not None:
        validate_classes_exist(ontology, get_classes_in_expressions(op.domain), "Domain")
        prop.domain = op.domain

    if op.range is not None:
        prop.range = op.range

    if op.new_name is not None and op.new_name != op.name:
        if op.new_name in ontology.data_properties:
            msg = f"Cannot rename: data property '{op.new_name}' already exists"
            raise ValueError(msg)

        del ontology.data_properties[op.name]
        prop.name = op.new_name
        ontology.data_properties[op.new_name] = prop

    return ontology


def _delete_data_property(op: DeleteDataProperty, ontology: Ontology) -> Ontology:
    """Delete a data property from the ontology."""
    if op.name not in ontology.data_properties:
        msg = f"Data property '{op.name}' does not exist"
        raise KeyError(msg)

    del ontology.data_properties[op.name]
    return ontology


def _add_object_property(op: AddObjectProperty, ontology: Ontology) -> Ontology:
    """Add a new object property to the ontology."""
    if op.name in ontology.object_properties:
        msg = f"Object property '{op.name}' already exists"
        raise ValueError(msg)

    validate_classes_exist(ontology, get_classes_in_expressions(op.domain), "Domain")
    validate_classes_exist(ontology, get_classes_in_expressions(op.range), "Range")

    ontology.object_properties[op.name] = ObjectProperty(
        name=op.name,
        description=op.description,
        domain=op.domain,
        range=op.range,
    )
    return ontology


def _update_object_property(op: UpdateObjectProperty, ontology: Ontology) -> Ontology:
    """Update an existing object property."""
    if op.name not in ontology.object_properties:
        msg = f"Object property '{op.name}' does not exist"
        raise KeyError(msg)

    prop = ontology.object_properties[op.name]

    if op.description is not None:
        prop.description = op.description

    if op.domain is not None:
        validate_classes_exist(ontology, get_classes_in_expressions(op.domain), "Domain")
        prop.domain = op.domain

    if op.range is not None:
        validate_classes_exist(ontology, get_classes_in_expressions(op.range), "Range")
        prop.range = op.range

    if op.new_name is not None and op.new_name != op.name:
        if op.new_name in ontology.object_properties:
            msg = f"Cannot rename: object property '{op.new_name}' already exists"
            raise ValueError(msg)

        del ontology.object_properties[op.name]
        prop.name = op.new_name
        ontology.object_properties[op.new_name] = prop

    return ontology


def _delete_object_property(op: DeleteObjectProperty, ontology: Ontology) -> Ontology:
    """Delete an object property from the ontology."""
    if op.name not in ontology.object_properties:
        msg = f"Object property '{op.name}' does not exist"
        raise KeyError(msg)

    del ontology.object_properties[op.name]
    return ontology


_OP_HANDLERS = {
    AddClass: _add_class,
    UpdateClass: _update_class,
    DeleteClass: _delete_class,
    MergeClasses: _merge_classes,
    AddDataProperty: _add_data_property,
    UpdateDataProperty: _update_data_property,
    DeleteDataProperty: _delete_data_property,
    AddObjectProperty: _add_object_property,
    UpdateObjectProperty: _update_object_property,
    DeleteObjectProperty: _delete_object_property,
}


def execute_op(op: Operation, ontology: Ontology) -> Ontology:
    """Execute a single operation on the ontology."""
    return _OP_HANDLERS[type(op)](op, ontology)


def execute_ops(ontology: Ontology, ops: list[Operation]) -> Ontology:
    """Execute a sequence of operations on the ontology."""
    ontology = ontology.clone()

    for i, op in enumerate(ops):
        try:
            ontology = execute_op(op, ontology)
        except (ValueError, KeyError) as e:
            raise OperationFailedError(i, op, e) from e

    return ontology
