"""Change metrics for measuring ontology evolution quality."""

from collections import defaultdict
from collections.abc import Sequence

from pydantic import BaseModel, Field, computed_field

from ontology_hydra.ontology.models import ClassName, Ontology, PropertyName
from ontology_hydra.ontology.revision.diff import OntologyDiff, diff_ontology
from ontology_hydra.ontology.revision.operations import Operation


class OperationCounts(BaseModel):
    """Counts of operations by type."""

    add_class: int = 0
    """Number of add_class operations."""
    add_data_prop: int = 0
    """Number of add_data_prop operations."""
    add_object_prop: int = 0
    """Number of add_object_prop operations."""
    update_class: int = 0
    """Number of update_class operations."""
    update_data_prop: int = 0
    """Number of update_data_prop operations."""
    update_object_prop: int = 0
    """Number of update_object_prop operations."""
    del_class: int = 0
    """Number of del_class operations."""
    del_data_prop: int = 0
    """Number of del_data_prop operations."""
    del_object_prop: int = 0
    """Number of del_object_prop operations."""
    merge_classes: int = 0
    """Number of merge_classes operations."""

    @computed_field
    @property
    def total_add(self) -> int:
        """Total additive operations."""
        return self.add_class + self.add_data_prop + self.add_object_prop

    @computed_field
    @property
    def total_update(self) -> int:
        """Total update/modify operations."""
        return self.update_class + self.update_data_prop + self.update_object_prop

    @computed_field
    @property
    def total_delete(self) -> int:
        """Total delete operations."""
        return self.del_class + self.del_data_prop + self.del_object_prop

    @computed_field
    @property
    def total_non_additive(self) -> int:
        """Total non-additive operations (update + delete + merge)."""
        return self.total_update + self.total_delete + self.merge_classes

    @computed_field
    @property
    def total(self) -> int:
        """Total operation count."""
        return self.total_add + self.total_non_additive

    @computed_field
    @property
    def add_ratio(self) -> float:
        """Ratio of additive to total operations."""
        return self.total_add / self.total if self.total > 0 else 0.0

    @computed_field
    @property
    def non_additive_ratio(self) -> float:
        """Ratio of non-additive to total operations."""
        return self.total_non_additive / self.total if self.total > 0 else 0.0

    def summary(self) -> str:
        """Human-readable summary."""
        parts = []
        if self.total_add > 0:
            parts.append(f"+{self.total_add} add")
        if self.total_update > 0:
            parts.append(f"~{self.total_update} update")
        if self.total_delete > 0:
            parts.append(f"-{self.total_delete} delete")
        if self.merge_classes > 0:
            parts.append(f"⊕{self.merge_classes} merge")

        if not parts:
            return "No operations"

        ratio_str = f"({self.add_ratio:.0%} additive)"
        return ", ".join(parts) + f" {ratio_str}"


class ChangeMetrics(BaseModel):
    """Metrics describing changes made during an evolution step."""

    # Operation counts
    operation_counts: OperationCounts
    """Breakdown of operations by type."""

    # Entities touched
    classes_added: list[ClassName] = Field(default_factory=list)
    """Names of classes that were added."""
    classes_modified: list[ClassName] = Field(default_factory=list)
    """Names of classes that were modified."""
    classes_removed: list[ClassName] = Field(default_factory=list)
    """Names of classes that were removed."""
    data_properties_added: list[PropertyName] = Field(default_factory=list)
    """Names of data properties that were added."""
    data_properties_modified: list[PropertyName] = Field(default_factory=list)
    """Names of data properties that were modified."""
    data_properties_removed: list[PropertyName] = Field(default_factory=list)
    """Names of data properties that were removed."""
    object_properties_added: list[PropertyName] = Field(default_factory=list)
    """Names of object properties that were added."""
    object_properties_modified: list[PropertyName] = Field(default_factory=list)
    """Names of object properties that were modified."""
    object_properties_removed: list[PropertyName] = Field(default_factory=list)
    """Names of object properties that were removed."""

    # Focus metrics
    unique_classes_touched: int = 0
    """Number of unique classes that were added, modified, or removed."""
    unique_properties_touched: int = 0
    """Number of unique properties that were added, modified, or removed."""
    scatter_score: float = 0.0
    """How scattered changes are across the hierarchy (higher = more scattered)."""

    # Retry/validation metrics
    retry_count: int = 0
    """Number of retries needed to get valid operations."""
    validation_failures: int = 0
    """Number of validation failures encountered."""

    @computed_field
    @property
    def total_entities_touched(self) -> int:
        """Total unique entities modified."""
        return self.unique_classes_touched + self.unique_properties_touched

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Operations: {self.operation_counts.summary()}",
            f"Touched: {self.unique_classes_touched} classes, {self.unique_properties_touched} properties",
        ]
        if self.scatter_score > 0:
            lines.append(f"Scatter score: {self.scatter_score:.2f}")
        if self.retry_count > 0:
            lines.append(f"Retries: {self.retry_count}")
        return "\n".join(lines)


def count_operations(operations: Sequence[Operation]) -> OperationCounts:
    """Count operations by type from a sequence of operations."""
    counts = OperationCounts()

    for op in operations:
        match op.op:
            case "add_class":
                counts.add_class += 1
            case "add_data_prop":
                counts.add_data_prop += 1
            case "add_object_prop":
                counts.add_object_prop += 1
            case "update_class":
                counts.update_class += 1
            case "update_data_prop":
                counts.update_data_prop += 1
            case "update_object_prop":
                counts.update_object_prop += 1
            case "del_class":
                counts.del_class += 1
            case "del_data_prop":
                counts.del_data_prop += 1
            case "del_object_prop":
                counts.del_object_prop += 1
            case "merge_classes":
                counts.merge_classes += 1

    return counts


def _compute_scatter_score(ontology: Ontology, touched_classes: set[ClassName]) -> float:
    """
    Compute how scattered the changes are across the class hierarchy.

    Lower score = changes are focused in related areas
    Higher score = changes are scattered across unrelated parts

    The score is based on the average distance between touched classes
    in the hierarchy graph.
    """
    if len(touched_classes) <= 1:
        return 0.0

    # Build parent-child adjacency for distance calculation
    # We'll use BFS to find shortest paths between touched classes
    adjacency: dict[ClassName, set[ClassName]] = defaultdict(set)
    for cls in ontology.classes.values():
        for parent in cls.sub_class_of:
            adjacency[cls.name].add(parent)
            adjacency[parent].add(cls.name)

    def bfs_distance(start: ClassName, end: ClassName) -> int:
        """Find shortest path distance between two classes."""
        if start == end:
            return 0
        if start not in ontology.classes or end not in ontology.classes:
            return 999  # Large distance for missing classes

        visited = {start}
        queue = [(start, 0)]

        while queue:
            current, dist = queue.pop(0)
            for neighbor in adjacency.get(current, set()):
                if neighbor == end:
                    return dist + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))

        return 999  # Not connected

    # Compute average pairwise distance
    touched_list = list(touched_classes)
    total_distance = 0
    pair_count = 0

    for i, c1 in enumerate(touched_list):
        for c2 in touched_list[i + 1 :]:
            total_distance += bfs_distance(c1, c2)
            pair_count += 1

    if pair_count == 0:
        return 0.0

    avg_distance = total_distance / pair_count

    # Normalize: 1-2 distance is focused, 3+ is scattered
    # Return a score where 0 = focused, higher = scattered
    return max(0.0, avg_distance - 1.0)


def compute_change_metrics(
    operations: Sequence[Operation],
    old_ontology: Ontology,
    new_ontology: Ontology,
    retry_count: int = 0,
    validation_failures: int = 0,
) -> ChangeMetrics:
    """
    Compute change metrics from operations and resulting ontologies.

    Args:
        operations: The operations that were executed
        old_ontology: Ontology state before operations
        new_ontology: Ontology state after operations
        retry_count: Number of retries needed to get valid operations
        validation_failures: Number of validation failures encountered
    """
    diff = diff_ontology(old_ontology, new_ontology)
    return compute_change_metrics_from_diff(
        diff, new_ontology, operations, retry_count, validation_failures
    )


def compute_change_metrics_from_diff(
    diff: OntologyDiff,
    ontology: Ontology,
    operations: Sequence[Operation] | None = None,
    retry_count: int = 0,
    validation_failures: int = 0,
) -> ChangeMetrics:
    """
    Compute change metrics from an existing diff.

    Useful when you already have the diff computed and don't want to recompute.
    """
    op_counts = count_operations(operations) if operations else OperationCounts()

    # Compute unique entities touched
    unique_classes = (
        set(diff.classes_added) | set(diff.classes_modified) | set(diff.classes_removed)
    )
    unique_props = (
        set(diff.data_properties_added)
        | set(diff.data_properties_modified)
        | set(diff.data_properties_removed)
        | set(diff.object_properties_added)
        | set(diff.object_properties_modified)
        | set(diff.object_properties_removed)
    )

    # Compute scatter score
    existing_touched = unique_classes & set(ontology.classes.keys())
    scatter = _compute_scatter_score(ontology, existing_touched)

    return ChangeMetrics(
        operation_counts=op_counts,
        classes_added=diff.classes_added,
        classes_modified=diff.classes_modified,
        classes_removed=diff.classes_removed,
        data_properties_added=diff.data_properties_added,
        data_properties_modified=diff.data_properties_modified,
        data_properties_removed=diff.data_properties_removed,
        object_properties_added=diff.object_properties_added,
        object_properties_modified=diff.object_properties_modified,
        object_properties_removed=diff.object_properties_removed,
        unique_classes_touched=len(unique_classes),
        unique_properties_touched=len(unique_props),
        scatter_score=scatter,
        retry_count=retry_count,
        validation_failures=validation_failures,
    )
