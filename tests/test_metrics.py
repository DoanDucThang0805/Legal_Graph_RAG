import pytest

from backend.evaluation.metrics import f2_score, hit_at_k, mrr, precision, recall


def test_precision_perfect_match() -> None:
    assert precision(["a", "b"], ["a", "b"]) == 1.0


def test_precision_partial_match() -> None:
    assert precision(["a", "b", "c"], ["a", "x"]) == pytest.approx(1 / 3)


def test_precision_empty_predicted() -> None:
    assert precision([], ["a"]) == 0.0


def test_recall_perfect_match() -> None:
    assert recall(["a", "b"], ["a", "b"]) == 1.0


def test_recall_partial_match() -> None:
    assert recall(["a", "x"], ["a", "b", "c"]) == pytest.approx(1 / 3)


def test_recall_empty_ground_truth() -> None:
    assert recall(["a"], []) == 0.0


def test_f2_score_prioritizes_recall_and_returns_expected_value() -> None:
    assert f2_score(["a", "b"], ["a", "c", "d"]) == pytest.approx(5 / 14)


def test_f2_score_no_overlap_returns_zero() -> None:
    assert f2_score(["a"], ["b"]) == 0.0


def test_hit_at_k_has_hit_in_top_k() -> None:
    assert hit_at_k(["x", "a", "b"], ["a"], k=2) == 1.0


def test_hit_at_k_no_hit_outside_top_k() -> None:
    assert hit_at_k(["x", "a"], ["a"], k=1) == 0.0


def test_hit_at_k_non_positive_k() -> None:
    assert hit_at_k(["a"], ["a"], k=0) == 0.0
    assert hit_at_k(["a"], ["a"], k=-1) == 0.0


def test_mrr_hit_at_first_position() -> None:
    assert mrr(["a", "b"], ["a"]) == 1.0


def test_mrr_hit_at_later_position() -> None:
    assert mrr(["x", "y", "a"], ["a"]) == pytest.approx(1 / 3)


def test_mrr_no_hit() -> None:
    assert mrr(["x", "y"], ["a"]) == 0.0


def test_duplicate_predicted_does_not_inflate_precision() -> None:
    assert precision(["a", "a", "b"], ["a"]) == pytest.approx(1 / 2)


def test_duplicate_ground_truth_does_not_break_recall() -> None:
    assert recall(["a"], ["a", "a", "b"]) == pytest.approx(1 / 2)


def test_preserve_order_for_mrr_and_hit_at_k_after_dedup() -> None:
    predicted = ["x", "x", "a"]
    ground_truth = ["a"]

    assert hit_at_k(predicted, ground_truth, k=1) == 0.0
    assert hit_at_k(predicted, ground_truth, k=2) == 1.0
    assert mrr(predicted, ground_truth) == pytest.approx(1 / 2)


def test_none_and_empty_items_are_ignored() -> None:
    assert precision([None, "", " a ", "a"], ("a",)) == 1.0
