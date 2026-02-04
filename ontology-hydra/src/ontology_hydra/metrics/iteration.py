"""Iteration metrics for ontology changes."""

from collections.abc import Sequence

from pydantic import BaseModel, computed_field

from ontology_hydra.ontology.models import Ontology
from ontology_hydra.ontology.revision.diff import diff_ontology
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

from .models import Metric
from .ontology import build_metric, compute_class_value_maps


class OperationCounts(BaseModel):
    """Counts and ratios of operations by type."""

    add_class: int = 0
    add_data_prop: int = 0
    add_object_prop: int = 0
    update_class: int = 0
    update_data_prop: int = 0
    update_object_prop: int = 0
    del_class: int = 0
    del_data_prop: int = 0
    del_object_prop: int = 0
    merge_classes: int = 0

    @computed_field
    @property
    def total_add(self) -> int:
        return self.add_class + self.add_data_prop + self.add_object_prop

    @computed_field
    @property
    def total_update(self) -> int:
        return self.update_class + self.update_data_prop + self.update_object_prop

    @computed_field
    @property
    def total_delete(self) -> int:
        return self.del_class + self.del_data_prop + self.del_object_prop

    @computed_field
    @property
    def total(self) -> int:
        return self.total_add + self.total_update + self.total_delete + self.merge_classes

    @computed_field
    @property
    def add_ratio(self) -> float:
        return self.total_add / self.total if self.total else 0.0

    @computed_field
    @property
    def update_ratio(self) -> float:
        return self.total_update / self.total if self.total else 0.0

    @computed_field
    @property
    def delete_ratio(self) -> float:
        return self.total_delete / self.total if self.total else 0.0

    @computed_field
    @property
    def merge_ratio(self) -> float:
        return self.merge_classes / self.total if self.total else 0.0


class IterationMetrics(BaseModel):
    """Metrics describing a single iteration."""

    class ChangeCounts(BaseModel):
        """Counts of entity changes by type."""

        classes_added: int
        classes_removed: int
        classes_modified: int
        data_properties_added: int
        data_properties_removed: int
        data_properties_modified: int
        object_properties_added: int
        object_properties_removed: int
        object_properties_modified: int

    class Touch(BaseModel):
        """Counts of unique entities touched."""

        touched_classes: int
        touched_properties: int

    class Ratios(BaseModel):
        """Ratios computed from the previous snapshot."""

        touched_class_ratio: float
        touched_property_ratio: float
        class_add_ratio: float
        class_remove_ratio: float
        data_property_add_ratio: float
        data_property_remove_ratio: float
        object_property_add_ratio: float
        object_property_remove_ratio: float

    class UpdateCounts(BaseModel):
        """Counts of update subtypes from operations."""

        class_renames: int
        class_description_updates: int
        class_superclass_updates: int
        data_property_renames: int
        data_property_description_updates: int
        data_property_domain_updates: int
        data_property_range_updates: int
        object_property_renames: int
        object_property_description_updates: int
        object_property_domain_updates: int
        object_property_range_updates: int

    class Deltas(BaseModel):
        """Distribution deltas between snapshots."""

        merge_size: Metric
        depth_delta: Metric
        subclasses_delta: Metric
        superclasses_delta: Metric
        data_props_per_class_delta: Metric
        object_props_out_per_class_delta: Metric
        object_props_in_per_class_delta: Metric

    operation_counts: OperationCounts
    changes: ChangeCounts
    touch: Touch
    ratios: Ratios
    updates: UpdateCounts
    deltas: Deltas


def _ratio(numerator: int, denominator: int) -> float:
    """Safe ratio helper with zero guard."""
    return numerator / denominator if denominator else 0.0


def _delta_values(old_map, new_map):
    """Delta values for keys shared between two maps."""
    shared = old_map.keys() & new_map.keys()
    return [new_map[name] - old_map[name] for name in shared]


def compute_iteration_metrics(  # noqa: C901
    operations: Sequence[Operation] | None,
    old_ontology: Ontology,
    new_ontology: Ontology,
) -> IterationMetrics:
    """Compute iteration metrics from operations and ontology snapshots."""
    diff = diff_ontology(old_ontology, new_ontology)
    operations = operations or []
    op_counts = OperationCounts()
    class_renames = 0
    class_description_updates = 0
    class_superclass_updates = 0
    data_property_renames = 0
    data_property_description_updates = 0
    data_property_domain_updates = 0
    data_property_range_updates = 0
    object_property_renames = 0
    object_property_description_updates = 0
    object_property_domain_updates = 0
    object_property_range_updates = 0
    merge_sizes = []

    for op in operations:
        match op:
            case AddClass():
                op_counts.add_class += 1
            case UpdateClass():
                op_counts.update_class += 1
                if op.new_name is not None:
                    class_renames += 1
                if op.description is not None:
                    class_description_updates += 1
                if op.sub_class_of is not None:
                    class_superclass_updates += 1
            case DeleteClass():
                op_counts.del_class += 1
            case MergeClasses():
                op_counts.merge_classes += 1
                merge_sizes.append(len(op.source_classes))
            case AddDataProperty():
                op_counts.add_data_prop += 1
            case UpdateDataProperty():
                op_counts.update_data_prop += 1
                if op.new_name is not None:
                    data_property_renames += 1
                if op.description is not None:
                    data_property_description_updates += 1
                if op.domain is not None:
                    data_property_domain_updates += 1
                if op.range is not None:
                    data_property_range_updates += 1
            case DeleteDataProperty():
                op_counts.del_data_prop += 1
            case AddObjectProperty():
                op_counts.add_object_prop += 1
            case UpdateObjectProperty():
                op_counts.update_object_prop += 1
                if op.new_name is not None:
                    object_property_renames += 1
                if op.description is not None:
                    object_property_description_updates += 1
                if op.domain is not None:
                    object_property_domain_updates += 1
                if op.range is not None:
                    object_property_range_updates += 1
            case DeleteObjectProperty():
                op_counts.del_object_prop += 1

    classes_added = len(diff.classes_added)
    classes_modified = len(diff.classes_modified)
    classes_removed = len(diff.classes_removed)
    data_props_added = len(diff.data_properties_added)
    data_props_modified = len(diff.data_properties_modified)
    data_props_removed = len(diff.data_properties_removed)
    object_props_added = len(diff.object_properties_added)
    object_props_modified = len(diff.object_properties_modified)
    object_props_removed = len(diff.object_properties_removed)

    touched_classes = len(
        set(diff.classes_added) | set(diff.classes_modified) | set(diff.classes_removed)
    )
    touched_properties = len(
        set(diff.data_properties_added)
        | set(diff.data_properties_modified)
        | set(diff.data_properties_removed)
        | set(diff.object_properties_added)
        | set(diff.object_properties_modified)
        | set(diff.object_properties_removed)
    )

    prev_class_count = len(old_ontology.classes)
    prev_data_property_count = len(old_ontology.data_properties)
    prev_object_property_count = len(old_ontology.object_properties)
    prev_property_count = prev_data_property_count + prev_object_property_count

    (
        old_depths,
        old_subclasses,
        old_superclasses,
        old_data_props,
        old_object_out,
        old_object_in,
    ) = compute_class_value_maps(old_ontology)
    (
        new_depths,
        new_subclasses,
        new_superclasses,
        new_data_props,
        new_object_out,
        new_object_in,
    ) = compute_class_value_maps(new_ontology)

    return IterationMetrics(
        operation_counts=op_counts,
        changes=IterationMetrics.ChangeCounts(
            classes_added=classes_added,
            classes_removed=classes_removed,
            classes_modified=classes_modified,
            data_properties_added=data_props_added,
            data_properties_removed=data_props_removed,
            data_properties_modified=data_props_modified,
            object_properties_added=object_props_added,
            object_properties_removed=object_props_removed,
            object_properties_modified=object_props_modified,
        ),
        touch=IterationMetrics.Touch(
            touched_classes=touched_classes,
            touched_properties=touched_properties,
        ),
        ratios=IterationMetrics.Ratios(
            touched_class_ratio=_ratio(touched_classes, prev_class_count),
            touched_property_ratio=_ratio(touched_properties, prev_property_count),
            class_add_ratio=_ratio(classes_added, prev_class_count),
            class_remove_ratio=_ratio(classes_removed, prev_class_count),
            data_property_add_ratio=_ratio(data_props_added, prev_data_property_count),
            data_property_remove_ratio=_ratio(data_props_removed, prev_data_property_count),
            object_property_add_ratio=_ratio(object_props_added, prev_object_property_count),
            object_property_remove_ratio=_ratio(object_props_removed, prev_object_property_count),
        ),
        updates=IterationMetrics.UpdateCounts(
            class_renames=class_renames,
            class_description_updates=class_description_updates,
            class_superclass_updates=class_superclass_updates,
            data_property_renames=data_property_renames,
            data_property_description_updates=data_property_description_updates,
            data_property_domain_updates=data_property_domain_updates,
            data_property_range_updates=data_property_range_updates,
            object_property_renames=object_property_renames,
            object_property_description_updates=object_property_description_updates,
            object_property_domain_updates=object_property_domain_updates,
            object_property_range_updates=object_property_range_updates,
        ),
        deltas=IterationMetrics.Deltas(
            merge_size=build_metric(merge_sizes),
            depth_delta=build_metric(_delta_values(old_depths, new_depths)),
            subclasses_delta=build_metric(_delta_values(old_subclasses, new_subclasses)),
            superclasses_delta=build_metric(_delta_values(old_superclasses, new_superclasses)),
            data_props_per_class_delta=build_metric(_delta_values(old_data_props, new_data_props)),
            object_props_out_per_class_delta=build_metric(
                _delta_values(old_object_out, new_object_out)
            ),
            object_props_in_per_class_delta=build_metric(
                _delta_values(old_object_in, new_object_in)
            ),
        ),
    )
