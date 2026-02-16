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


def _extract_affected_classes(
    operations: Sequence[Operation],
    old_ontology: Ontology,
) -> set[ClassName]:
    """Extract all class names touched by the operations."""
    affected: set[ClassName] = set()

    for op in operations:
        match op:
            case AddClass():
                affected.update({op.name, *op.sub_class_of})
            case UpdateClass():
                affected.add(op.name)
                if op.new_name is not None:
                    affected.add(op.new_name)
                if op.sub_class_of is not None:
                    affected.update(op.sub_class_of)
            case DeleteClass():
                affected.add(op.name)
            case MergeClasses():
                affected.update({*op.source_classes, op.target_name})
            case AddDataProperty():
                affected.update(get_classes_in_expressions(op.domain))
            case UpdateDataProperty():
                if op.domain is not None:
                    affected.update(get_classes_in_expressions(op.domain))
                if op.name in old_ontology.data_properties:
                    affected.update(get_classes_in_expressions(old_ontology.data_properties[op.name].domain))
            case DeleteDataProperty():
                if op.name in old_ontology.data_properties:
                    affected.update(get_classes_in_expressions(old_ontology.data_properties[op.name].domain))
            case AddObjectProperty():
                affected.update(get_classes_in_expressions(op.domain))
                affected.update(get_classes_in_expressions(op.range))
            case UpdateObjectProperty():
                if op.domain is not None:
                    affected.update(get_classes_in_expressions(op.domain))
                if op.range is not None:
                    affected.update(get_classes_in_expressions(op.range))
                if op.name in old_ontology.object_properties:
                    old_prop = old_ontology.object_properties[op.name]
                    affected.update(get_classes_in_expressions(old_prop.domain))
                    affected.update(get_classes_in_expressions(old_prop.range))
            case DeleteObjectProperty():
                if op.name in old_ontology.object_properties:
                    old_prop = old_ontology.object_properties[op.name]
                    affected.update(get_classes_in_expressions(old_prop.domain))
                    affected.update(get_classes_in_expressions(old_prop.range))

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

    affected_in_graph = affected & set(graph.nodes)
    if len(affected_in_graph) <= 1:
        return 1.0 if affected_in_graph else None

    if graph.number_of_nodes() < 2:
        return 1.0

    # Batch-compute all pairwise distances (only reachable pairs are included)
    all_distances = dict(nx.all_pairs_shortest_path_length(graph))

    diameter = max(d for dists in all_distances.values() for d in dists.values())
    if diameter == 0:
        return 1.0

    # Mean pairwise distance among affected nodes (disconnected pairs get diameter)
    distances = [
        all_distances[a].get(b, diameter)
        for a, b in combinations(affected_in_graph, 2)
    ]

    return 1.0 - (mean(distances) / diameter)
