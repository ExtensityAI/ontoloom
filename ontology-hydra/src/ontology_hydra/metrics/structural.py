"""Structural metrics for measuring ontology shape and health."""

from collections import defaultdict
from statistics import mean

from pydantic import BaseModel

from ontology_hydra.ontology.models import ClassName, Ontology
from ontology_hydra.ontology.revision.helpers import get_classes_in_expressions


class StructuralMetrics(BaseModel):
    """Metrics describing the structure and shape of an ontology."""

    # Basic counts
    class_count: int
    """Total number of classes in the ontology."""
    data_property_count: int
    """Total number of data properties."""
    object_property_count: int
    """Total number of object properties."""

    # Hierarchy metrics
    root_class_count: int
    """Classes with no superclass except Thing."""
    leaf_class_count: int
    """Classes with no subclasses."""
    max_depth: int
    """Deepest path from Thing to any leaf class."""
    avg_depth: float
    """Mean depth across all classes."""
    avg_branching_factor: float
    """Average number of children per non-leaf class."""

    # Connectivity metrics
    orphan_class_count: int
    """Classes with no incoming/outgoing object properties."""
    classes_with_data_properties: int
    """Number of classes that have at least one data property."""
    property_coverage: float
    """Fraction of classes (excluding Thing) with at least one data property."""
    relationship_density: float
    """Object properties divided by classes squared (normalized connectivity)."""

    # Quality indicators
    classes_with_empty_definition: int
    """Classes whose definition field is empty or whitespace-only."""
    classes_with_constraints: int
    """Classes that have constraints specified."""
    properties_with_thing_domain: int
    """Properties with overly broad domain (only Thing)."""

    def summary(self) -> str:
        """Human-readable summary of key metrics."""
        lines = [
            f"Classes: {self.class_count} ({self.root_class_count} roots, {self.leaf_class_count} leaves)",
            f"Properties: {self.data_property_count} data, {self.object_property_count} object",
            f"Hierarchy: max depth {self.max_depth}, avg depth {self.avg_depth:.1f}, branching {self.avg_branching_factor:.1f}",
            f"Coverage: {self.property_coverage:.0%} classes have data properties",
            f"Orphans: {self.orphan_class_count} classes with no object property connections",
        ]
        if self.classes_with_empty_definition > 0:
            lines.append(
                f"Quality: {self.classes_with_empty_definition} classes with empty definitions"
            )
        return "\n".join(lines)


def _compute_depths(ontology: Ontology) -> dict[ClassName, int]:
    """Compute depth of each class from Thing (depth 0)."""
    depths: dict[ClassName, int] = {}
    thing = ClassName("Thing")

    # Build parent -> children mapping
    children: dict[ClassName, list[ClassName]] = defaultdict(list)
    for cls in ontology.classes.values():
        for parent in cls.sub_class_of:
            children[parent].append(cls.name)

    # BFS from Thing
    queue = [(thing, 0)]
    visited = set()

    while queue:
        current, depth = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        depths[current] = depth

        for child in children.get(current, []):
            if child not in visited:
                queue.append((child, depth + 1))

    # Handle classes not reachable from Thing (shouldn't happen in valid ontology)
    for name in ontology.classes:
        if name not in depths:
            depths[name] = 0

    return depths


def _find_leaf_classes(ontology: Ontology) -> set[ClassName]:
    """Find classes with no subclasses."""
    parents: set[ClassName] = set()
    for cls in ontology.classes.values():
        parents.update(cls.sub_class_of)

    return set(ontology.classes.keys()) - parents


def _find_root_classes(ontology: Ontology) -> set[ClassName]:
    """Find classes whose only superclass is Thing (or no superclass)."""
    thing = ClassName("Thing")
    roots: set[ClassName] = set()

    for cls in ontology.classes.values():
        if cls.name == thing:
            continue
        # Root if no superclass or only Thing as superclass
        non_thing_parents = [p for p in cls.sub_class_of if p != thing]
        if len(non_thing_parents) == 0:
            roots.add(cls.name)

    return roots


def _find_orphan_classes(ontology: Ontology) -> set[ClassName]:
    """Find classes not referenced in any object property domain or range."""
    referenced: set[ClassName] = set()

    for prop in ontology.object_properties.values():
        referenced.update(get_classes_in_expressions(prop.domain))
        referenced.update(get_classes_in_expressions(prop.range))

    # Thing is not considered orphan
    thing = ClassName("Thing")
    all_classes = set(ontology.classes.keys()) - {thing}

    return all_classes - referenced


def _find_classes_with_data_properties(ontology: Ontology) -> set[ClassName]:
    """Find classes that have at least one data property in their domain."""
    classes_with_props: set[ClassName] = set()

    for prop in ontology.data_properties.values():
        classes_with_props.update(get_classes_in_expressions(prop.domain))

    return classes_with_props


def _count_thing_domain_properties(ontology: Ontology) -> int:
    """Count properties with Thing as their only domain (overly broad)."""
    thing = ClassName("Thing")
    count = 0

    for prop in ontology.data_properties.values():
        domain_classes = get_classes_in_expressions(prop.domain)
        if domain_classes == {thing}:
            count += 1

    for prop in ontology.object_properties.values():
        domain_classes = get_classes_in_expressions(prop.domain)
        if domain_classes == {thing}:
            count += 1

    return count


def compute_structural_metrics(ontology: Ontology) -> StructuralMetrics:
    """Compute all structural metrics for an ontology."""
    thing = ClassName("Thing")

    # Basic counts
    class_count = len(ontology.classes)
    data_property_count = len(ontology.data_properties)
    object_property_count = len(ontology.object_properties)

    # Hierarchy metrics
    roots = _find_root_classes(ontology)
    leaves = _find_leaf_classes(ontology)
    depths = _compute_depths(ontology)

    max_depth = max(depths.values()) if depths else 0
    avg_depth = mean(depths.values()) if depths else 0.0

    # Branching factor: average children per non-leaf class
    children_count: dict[ClassName, int] = defaultdict(int)
    for cls in ontology.classes.values():
        for parent in cls.sub_class_of:
            children_count[parent] += 1

    non_leaf_classes = set(ontology.classes.keys()) - leaves
    if non_leaf_classes:
        avg_branching = mean(children_count.get(c, 0) for c in non_leaf_classes)
    else:
        avg_branching = 0.0

    # Connectivity
    orphans = _find_orphan_classes(ontology)
    classes_with_data_props = _find_classes_with_data_properties(ontology)

    # Exclude Thing from coverage calculation
    non_thing_classes = class_count - 1 if thing in ontology.classes else class_count
    if non_thing_classes > 0:
        property_coverage = len(classes_with_data_props - {thing}) / non_thing_classes
    else:
        property_coverage = 0.0

    # Relationship density: object_properties / (classes^2)
    if class_count > 1:
        relationship_density = object_property_count / (class_count * class_count)
    else:
        relationship_density = 0.0

    # Quality indicators
    empty_definitions = sum(
        1
        for cls in ontology.classes.values()
        if not cls.description.definition or cls.description.definition.strip() == ""
    )
    with_constraints = sum(
        1
        for cls in ontology.classes.values()
        if cls.description.constraints and cls.description.constraints.strip()
    )
    thing_domain_props = _count_thing_domain_properties(ontology)

    return StructuralMetrics(
        class_count=class_count,
        data_property_count=data_property_count,
        object_property_count=object_property_count,
        root_class_count=len(roots),
        leaf_class_count=len(leaves),
        max_depth=max_depth,
        avg_depth=avg_depth,
        avg_branching_factor=avg_branching,
        orphan_class_count=len(orphans),
        classes_with_data_properties=len(classes_with_data_props),
        property_coverage=property_coverage,
        relationship_density=relationship_density,
        classes_with_empty_definition=empty_definitions,
        classes_with_constraints=with_constraints,
        properties_with_thing_domain=thing_domain_props,
    )
