"""Utility metrics for article-level retrieval evaluation."""

from collections.abc import Iterable
from typing import TypeAlias


MetricItem: TypeAlias = object


def _deduplicate_items(items: Iterable[MetricItem] | MetricItem | None) -> list[str]:
    """Return non-empty string items, deduplicated while preserving order."""
    if items is None:
        return []

    if isinstance(items, str):
        iterable: Iterable[MetricItem] = [items]
    else:
        try:
            iterable = iter(items)  # type: ignore[arg-type]
        except TypeError:
            iterable = [items]

    seen: set[str] = set()
    result: list[str] = []

    for item in iterable:
        if item is None:
            continue

        value = str(item).strip()
        if not value or value in seen:
            continue

        # Giữ thứ tự xuất hiện đầu tiên vì hit@k và MRR phụ thuộc ranking.
        seen.add(value)
        result.append(value)

    return result


def precision(predicted: Iterable[MetricItem] | MetricItem | None, ground_truth: Iterable[MetricItem] | MetricItem | None) -> float:
    """Compute article-level precision after order-preserving deduplication."""
    predicted_items = _deduplicate_items(predicted)
    if not predicted_items:
        return 0.0

    ground_truth_items = set(_deduplicate_items(ground_truth))
    if not ground_truth_items:
        return 0.0

    correct_count = sum(1 for item in predicted_items if item in ground_truth_items)
    return correct_count / len(predicted_items)


def recall(predicted: Iterable[MetricItem] | MetricItem | None, ground_truth: Iterable[MetricItem] | MetricItem | None) -> float:
    """Compute article-level recall after order-preserving deduplication."""
    ground_truth_items = _deduplicate_items(ground_truth)
    if not ground_truth_items:
        return 0.0

    predicted_items = set(_deduplicate_items(predicted))
    if not predicted_items:
        return 0.0

    found_count = sum(1 for item in ground_truth_items if item in predicted_items)
    return found_count / len(ground_truth_items)


def f2_score(predicted: Iterable[MetricItem] | MetricItem | None, ground_truth: Iterable[MetricItem] | MetricItem | None) -> float:
    """Compute F2 score, weighting recall higher than precision."""
    precision_value = precision(predicted, ground_truth)
    recall_value = recall(predicted, ground_truth)
    if precision_value == 0.0 and recall_value == 0.0:
        return 0.0

    beta_squared = 4.0
    numerator = (1.0 + beta_squared) * precision_value * recall_value
    denominator = beta_squared * precision_value + recall_value
    return numerator / denominator if denominator else 0.0


def hit_at_k(predicted: Iterable[MetricItem] | MetricItem | None, ground_truth: Iterable[MetricItem] | MetricItem | None, k: int) -> float:
    """Return 1.0 when at least one relevant item appears in the top-k predictions."""
    if k <= 0:
        return 0.0

    predicted_items = _deduplicate_items(predicted)
    ground_truth_items = set(_deduplicate_items(ground_truth))
    if not predicted_items or not ground_truth_items:
        return 0.0

    top_k_items = predicted_items[:k]
    return 1.0 if any(item in ground_truth_items for item in top_k_items) else 0.0


def mrr(predicted: Iterable[MetricItem] | MetricItem | None, ground_truth: Iterable[MetricItem] | MetricItem | None) -> float:
    """Compute mean reciprocal rank for a single query."""
    predicted_items = _deduplicate_items(predicted)
    ground_truth_items = set(_deduplicate_items(ground_truth))
    if not predicted_items or not ground_truth_items:
        return 0.0

    for rank, item in enumerate(predicted_items, start=1):
        if item in ground_truth_items:
            return 1.0 / rank

    return 0.0
