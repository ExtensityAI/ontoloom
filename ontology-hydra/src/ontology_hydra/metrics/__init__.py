"""Metrics for measuring ontology quality and evolution."""

from .changes import (
    ChangeMetrics,
    OperationCounts,
    compute_change_metrics,
    compute_change_metrics_from_diff,
    count_operations,
)
from .structural import (
    StructuralMetrics,
    compute_structural_metrics,
)

__all__ = [
    "ChangeMetrics",
    "OperationCounts",
    "StructuralMetrics",
    "compute_change_metrics",
    "compute_change_metrics_from_diff",
    "compute_structural_metrics",
    "count_operations",
]
