"""Edit locality metric — measures spatial clustering of edits in the class hierarchy."""

from collections.abc import Sequence
from itertools import combinations
from statistics import mean

import networkx as nx

from ontology_hydra.ontology.models import ClassName, Ontology
from ontology_hydra.ontology.revision.helpers import get_classes_in_expressions
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


def _build_hierarchy_graph(ontology: Ontology) -> nx.Graph:
    """Build an undirected graph from the class hierarchy (sub_class_of edges)."""
    g = nx.Graph()
    for name, cls in ontology.classes.items():
        g.add_node(name)
        for parent in cls.sub_class_of:
            if parent in ontology.classes:
                g.add_edge(name, parent)
    return g


def _classes_from_class_op(op: Operation) -> set[ClassName]:
    """Extract affected class names from a class-level operation."""
    match op:
        case AddClass():
            return {op.name, *op.sub_class_of}
        case UpdateClass():
            result = {op.name}
            if op.new_name is not None:
                result.add(op.new_name)
            if op.sub_class_of is not None:
                result.update(op.sub_class_of)
            return result
        case DeleteClass():
            return {op.name}
        case MergeClasses():
            return {*op.source_classes, op.target_name}
    return set()


def _classes_from_data_prop_op(op: Operation, old_ontology: Ontology) -> set[ClassName]:
    """Extract affected class names from a data property operation."""
    result: set[ClassName] = set()
    match op:
        case AddDataProperty():
            result.update(get_classes_in_expressions(op.domain))
        case UpdateDataProperty():
            if op.domain is not None:
                result.update(get_classes_in_expressions(op.domain))
            if op.name in old_ontology.data_properties:
                result.update(get_classes_in_expressions(old_ontology.data_properties[op.name].domain))
        case DeleteDataProperty():
            if op.name in old_ontology.data_properties:
                result.update(get_classes_in_expressions(old_ontology.data_properties[op.name].domain))
    return result


def _classes_from_object_prop_op(op: Operation, old_ontology: Ontology) -> set[ClassName]:
    """Extract affected class names from an object property operation."""
    result: set[ClassName] = set()
    match op:
        case AddObjectProperty():
            result.update(get_classes_in_expressions(op.domain))
            result.update(get_classes_in_expressions(op.range))
        case UpdateObjectProperty():
            if op.domain is not None:
                result.update(get_classes_in_expressions(op.domain))
            if op.range is not None:
                result.update(get_classes_in_expressions(op.range))
            if op.name in old_ontology.object_properties:
                old_prop = old_ontology.object_properties[op.name]
                result.update(get_classes_in_expressions(old_prop.domain))
                result.update(get_classes_in_expressions(old_prop.range))
        case DeleteObjectProperty():
            if op.name in old_ontology.object_properties:
                old_prop = old_ontology.object_properties[op.name]
                result.update(get_classes_in_expressions(old_prop.domain))
                result.update(get_classes_in_expressions(old_prop.range))
    return result


def _extract_affected_classes(
    operations: Sequence[Operation],
    old_ontology: Ontology,
) -> set[ClassName]:
    """Extract class names touched by each operation."""
    affected: set[ClassName] = set()
    for op in operations:
        affected |= _classes_from_class_op(op)
        affected |= _classes_from_data_prop_op(op, old_ontology)
        affected |= _classes_from_object_prop_op(op, old_ontology)
    return affected


def compute_edit_locality(
    operations: Sequence[Operation] | None,
    old_ontology: Ontology,
    new_ontology: Ontology,
) -> float | None:
    """Compute edit locality score (0-1) measuring spatial clustering of edits.

    Returns None if there are no operations or no affected classes in the graph.
    Returns 1.0 if only a single node is affected (maximally local).
    """
    if not operations:
        return None

    affected = _extract_affected_classes(operations, old_ontology)
    graph = _build_hierarchy_graph(new_ontology)

    # Filter to nodes actually present in the new ontology graph
    affected_in_graph = affected & set(graph.nodes)
    if len(affected_in_graph) == 0:
        return None
    if len(affected_in_graph) == 1:
        return 1.0

    # Compute graph diameter (longest shortest path across all connected components)
    if graph.number_of_nodes() < 2:
        return 1.0

    diameter = 0
    for component in nx.connected_components(graph):
        if len(component) >= 2:
            subgraph = graph.subgraph(component)
            diameter = max(diameter, nx.diameter(subgraph))

    if diameter == 0:
        return 1.0

    # Compute mean pairwise shortest path among affected nodes
    # Disconnected pairs get diameter distance
    distances: list[int] = []
    for a, b in combinations(affected_in_graph, 2):
        try:
            d = nx.shortest_path_length(graph, a, b)
        except nx.NetworkXNoPath:
            d = diameter
        distances.append(d)

    mean_distance = mean(distances)
    return 1.0 - (mean_distance / diameter)
