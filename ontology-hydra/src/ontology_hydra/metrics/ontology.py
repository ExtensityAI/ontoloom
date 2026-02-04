"""Ontology snapshot metrics."""

from collections import defaultdict, deque
from statistics import mean, median, pstdev

from pydantic import BaseModel

from ontology_hydra.ontology.models import ClassName, IntersectionOf, Ontology
from ontology_hydra.ontology.revision.helpers import get_classes_in_expressions

from .models import Metric


class OntologyMetrics(BaseModel):
    """Snapshot metrics for an ontology."""

    class Counts(BaseModel):
        """Count-based snapshot metrics."""

        n_classes: int
        n_properties: int
        n_object_properties: int
        n_data_properties: int
        n_root_classes: int
        n_leaf_classes: int
        classes_with_no_properties: int

    class Distributions(BaseModel):
        """Distribution metrics for ontology structure and usage."""

        class_depth: Metric
        subclasses_per_class: Metric
        superclasses_per_class: Metric
        data_props_per_class: Metric
        object_props_out_per_class: Metric
        object_props_in_per_class: Metric
        data_prop_domain_arity: Metric
        object_prop_domain_arity: Metric
        object_prop_range_arity: Metric
        intersection_arity: Metric

    counts: Counts
    distributions: Distributions


def build_metric(values):
    """Build a Metric from a sequence of numeric values."""
    if not values:
        return Metric(min=0.0, max=0.0, mean=0.0, median=0.0, stdev=0.0, raw=[])
    raw = [float(v) for v in values]
    return Metric(
        min=min(raw),
        max=max(raw),
        mean=float(mean(raw)),
        median=float(median(raw)),
        stdev=float(pstdev(raw)) if len(raw) > 1 else 0.0,
        raw=raw,
    )


def _children_by_parent(ontology: Ontology):
    children = defaultdict(list)
    for cls in ontology.classes.values():
        for parent in cls.sub_class_of:
            children[parent].append(cls.name)
    return children


def _compute_depths(ontology: Ontology):
    thing = ClassName("Thing")
    children = _children_by_parent(ontology)
    depths = {}
    queue = deque([(thing, 0)])
    visited = set()

    while queue:
        current, depth = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        depths[current] = depth

        for child in children.get(current, []):
            if child not in visited:
                queue.append((child, depth + 1))

    for name in ontology.classes:
        if name not in depths:
            depths[name] = 0

    return depths


def _find_leaf_classes(ontology: Ontology):
    parents = set()
    for cls in ontology.classes.values():
        parents.update(cls.sub_class_of)
    return set(ontology.classes.keys()) - parents


def _find_root_classes(ontology: Ontology):
    thing = ClassName("Thing")
    roots = set()
    for cls in ontology.classes.values():
        if cls.name == thing:
            continue
        non_thing_parents = [p for p in cls.sub_class_of if p != thing]
        if not non_thing_parents:
            roots.add(cls.name)
    return roots


def _direct_subclass_counts(ontology: Ontology):
    children = _children_by_parent(ontology)
    counts = {}
    for name in ontology.classes:
        counts[name] = len(children.get(name, []))
    return counts


def _superclass_counts(ontology: Ontology):
    counts = {}
    for cls in ontology.classes.values():
        counts[cls.name] = len(cls.sub_class_of)
    return counts


def _data_props_per_class(ontology: Ontology):
    counts = defaultdict(int)
    for prop in ontology.data_properties.values():
        for cls in get_classes_in_expressions(prop.domain):
            counts[cls] += 1
    for name in ontology.classes:
        counts.setdefault(name, 0)
    return counts


def _object_props_out_per_class(ontology: Ontology):
    counts = defaultdict(int)
    for prop in ontology.object_properties.values():
        for cls in get_classes_in_expressions(prop.domain):
            counts[cls] += 1
    for name in ontology.classes:
        counts.setdefault(name, 0)
    return counts


def _object_props_in_per_class(ontology: Ontology):
    counts = defaultdict(int)
    for prop in ontology.object_properties.values():
        for cls in get_classes_in_expressions(prop.range):
            counts[cls] += 1
    for name in ontology.classes:
        counts.setdefault(name, 0)
    return counts


def _data_prop_domain_arity(ontology: Ontology):
    return [
        len(get_classes_in_expressions(prop.domain)) for prop in ontology.data_properties.values()
    ]


def _object_prop_domain_arity(ontology: Ontology):
    return [
        len(get_classes_in_expressions(prop.domain)) for prop in ontology.object_properties.values()
    ]


def _object_prop_range_arity(ontology: Ontology):
    return [
        len(get_classes_in_expressions(prop.range)) for prop in ontology.object_properties.values()
    ]


def _intersection_arities(ontology: Ontology):
    sizes = []
    for prop in ontology.data_properties.values():
        for expr in prop.domain:
            if isinstance(expr, IntersectionOf):
                sizes.append(len(expr.classes))
    for prop in ontology.object_properties.values():
        for expr in prop.domain:
            if isinstance(expr, IntersectionOf):
                sizes.append(len(expr.classes))
        for expr in prop.range:
            if isinstance(expr, IntersectionOf):
                sizes.append(len(expr.classes))
    return sizes


def compute_class_value_maps(ontology: Ontology):
    """Compute per-class value maps used in snapshot and iteration metrics."""
    return (
        _compute_depths(ontology),
        _direct_subclass_counts(ontology),
        _superclass_counts(ontology),
        _data_props_per_class(ontology),
        _object_props_out_per_class(ontology),
        _object_props_in_per_class(ontology),
    )


def compute_ontology_metrics(ontology: Ontology) -> OntologyMetrics:
    """Compute snapshot metrics for an ontology."""
    class_count = len(ontology.classes)
    data_property_count = len(ontology.data_properties)
    object_property_count = len(ontology.object_properties)
    property_count = data_property_count + object_property_count

    roots = _find_root_classes(ontology)
    leaves = _find_leaf_classes(ontology)
    depths, subclasses, superclasses, data_props, object_out, object_in = compute_class_value_maps(
        ontology
    )

    classes_with_no_props = sum(
        1
        for name in ontology.classes
        if data_props.get(name, 0) == 0
        and object_out.get(name, 0) == 0
        and object_in.get(name, 0) == 0
    )

    return OntologyMetrics(
        counts=OntologyMetrics.Counts(
            n_classes=class_count,
            n_properties=property_count,
            n_object_properties=object_property_count,
            n_data_properties=data_property_count,
            n_root_classes=len(roots),
            n_leaf_classes=len(leaves),
            classes_with_no_properties=classes_with_no_props,
        ),
        distributions=OntologyMetrics.Distributions(
            class_depth=build_metric(list(depths.values())),
            subclasses_per_class=build_metric(list(subclasses.values())),
            superclasses_per_class=build_metric(list(superclasses.values())),
            data_props_per_class=build_metric(list(data_props.values())),
            object_props_out_per_class=build_metric(list(object_out.values())),
            object_props_in_per_class=build_metric(list(object_in.values())),
            data_prop_domain_arity=build_metric(_data_prop_domain_arity(ontology)),
            object_prop_domain_arity=build_metric(_object_prop_domain_arity(ontology)),
            object_prop_range_arity=build_metric(_object_prop_range_arity(ontology)),
            intersection_arity=build_metric(_intersection_arities(ontology)),
        ),
    )
