"""Build weak-supervision training data for a reranker from retrieval logs."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import polars as pl


LOGGER = logging.getLogger(__name__)

DEFAULT_RETRIEVAL_RESULTS_PATH = Path(
    "data/outputs/error_analysis_v2_p6r6d_selector_tuning_threshold_aligned/"
    "config_soft_9_8/retrieval_results_p6r6_tightened.jsonl"
)
DEFAULT_LEGAL_ARTICLES_PATH = Path("data/processed/legal_articles.parquet")
DEFAULT_OUTPUT_PATH = Path("data/outputs/reranker_training_data.jsonl")
DEFAULT_SUMMARY_PATH = Path("data/outputs/reranker_training_data_summary.json")

POSITIVE_FIELD_NAMES = (
    "selected_article_ids",
    "selected_articles",
    "final_selected_article_ids",
    "final_selected_articles",
)
CANDIDATE_FIELD_NAMES = (
    "candidates",
    "candidate_articles",
    "retrieval_candidates",
    "hits",
    "retrieval_hits",
    "ranked_candidates",
    "fused_candidates",
    "rrf_candidates",
    "articles",
)
ARTICLE_ID_FIELD_NAMES = (
    "article_id",
    "legal_article_id",
    "canonical_article_id",
    "parent_article_id",
)
METADATA_FIELD_NAMES = ("metadata", "meta")


def build_reranker_training_data(
    retrieval_results_path: str | Path = DEFAULT_RETRIEVAL_RESULTS_PATH,
    legal_articles_path: str | Path = DEFAULT_LEGAL_ARTICLES_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    summary_path: str | Path = DEFAULT_SUMMARY_PATH,
    max_questions: int | None = None,
    max_hard_negatives: int = 5,
    min_positive_score: float | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create weak-supervision reranker samples from retrieval results.

    Positive labels are only accepted from selected article fields in the
    retrieval log and must exist in the canonical legal article registry.
    Hard negatives are mined from same-question retrieval candidates/hits.
    """

    retrieval_results_path = Path(retrieval_results_path)
    legal_articles_path = Path(legal_articles_path)
    output_path = Path(output_path)
    summary_path = Path(summary_path)

    _validate_build_options(max_questions, max_hard_negatives)
    _ensure_can_write(output_path, overwrite)
    _ensure_can_write(summary_path, overwrite)

    canonical_article_ids = _load_canonical_article_ids(legal_articles_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    summary = _new_summary(output_path, summary_path)
    samples: list[dict[str, Any]] = []

    for row_index, row in enumerate(_iter_jsonl(retrieval_results_path), start=1):
        if max_questions is not None and summary["total_questions_seen"] >= max_questions:
            break

        summary["total_questions_seen"] += 1
        question_id = _extract_question_id(row, row_index)
        query = _extract_query(row)

        positive_infos = _extract_positive_infos(row, canonical_article_ids)
        if min_positive_score is not None:
            positive_infos = [
                info for info in positive_infos if info.score is None or info.score >= min_positive_score
            ]

        if not positive_infos:
            _record_no_positive_or_invalid(row, canonical_article_ids, summary)
            continue

        invalid_positive_ids = _extract_invalid_positive_article_ids(row, canonical_article_ids)
        _record_invalid_ids(invalid_positive_ids, summary["invalid_positive_article_ids"])

        candidate_infos = _extract_candidate_infos(row, canonical_article_ids, summary)
        positive_ids = {info.article_id for info in positive_infos}
        hard_negative_ids = _dedupe(
            info.article_id for info in candidate_infos if info.article_id not in positive_ids
        )[:max_hard_negatives]

        if not hard_negative_ids:
            summary["questions_skipped_no_hard_negatives"] += 1
            LOGGER.info("Skip question %s because no valid hard negatives were found.", question_id)
            continue

        for positive_info in positive_infos:
            samples.append(
                {
                    "question_id": question_id,
                    "query": query,
                    "positive_article_id": positive_info.article_id,
                    "hard_negative_article_ids": hard_negative_ids,
                    "weak_label": True,
                    "label_source": "retrieval_selected_articles",
                    "metadata": {
                        "positive_rank": positive_info.rank,
                        "positive_score": positive_info.score,
                        "num_candidates": len(candidate_infos),
                        "num_hard_negatives": len(hard_negative_ids),
                    },
                }
            )

    _write_jsonl(output_path, samples)
    summary["samples_written"] = len(samples)
    summary["invalid_positive_article_ids"] = sorted(summary["invalid_positive_article_ids"])
    _write_json(summary_path, summary)
    return summary


class _ArticleInfo:
    def __init__(self, article_id: str, rank: int | None = None, score: float | None = None) -> None:
        self.article_id = article_id
        self.rank = rank
        self.score = score


def _load_canonical_article_ids(path: Path) -> set[str]:
    if not path.exists():
        raise FileNotFoundError(f"Legal articles parquet not found: {path}")

    frame = pl.read_parquet(path, columns=["article_id"])
    article_ids = {str(value) for value in frame["article_id"].drop_nulls().to_list() if str(value).strip()}
    if not article_ids:
        raise ValueError(f"No canonical article_id values found in {path}")
    return article_ids


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Retrieval results JSONL not found: {path}")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                LOGGER.warning("Skip invalid JSONL line %s in %s: %s", line_number, path, exc)
                continue
            if isinstance(value, dict):
                rows.append(value)
            else:
                LOGGER.warning("Skip non-object JSONL line %s in %s.", line_number, path)
    return rows


def _extract_positive_infos(row: dict[str, Any], canonical_article_ids: set[str]) -> list[_ArticleInfo]:
    infos: list[_ArticleInfo] = []
    for field_name in POSITIVE_FIELD_NAMES:
        raw_items = _as_list(row.get(field_name))
        for position, raw_item in enumerate(raw_items, start=1):
            article_id = _extract_article_id(raw_item, canonical_article_ids)
            if article_id is None:
                continue
            infos.append(_ArticleInfo(article_id=article_id, rank=_extract_rank(raw_item, position), score=_extract_score(raw_item)))
    return _dedupe_article_infos(infos)


def _extract_invalid_positive_article_ids(
    row: dict[str, Any],
    canonical_article_ids: set[str],
) -> list[str]:
    invalid_ids: list[str] = []
    for field_name in POSITIVE_FIELD_NAMES:
        for raw_item in _as_list(row.get(field_name)):
            raw_article_id = _extract_raw_article_id(raw_item)
            if raw_article_id and raw_article_id not in canonical_article_ids:
                invalid_ids.append(raw_article_id)
    return _dedupe(invalid_ids)


def _extract_candidate_infos(
    row: dict[str, Any],
    canonical_article_ids: set[str],
    summary: dict[str, Any],
) -> list[_ArticleInfo]:
    infos: list[_ArticleInfo] = []
    invalid_negative_count = 0

    for field_name in CANDIDATE_FIELD_NAMES:
        raw_items = _as_list(row.get(field_name))
        for position, raw_item in enumerate(raw_items, start=1):
            article_id = _extract_article_id(raw_item, canonical_article_ids)
            if article_id is None:
                if _extract_raw_article_id(raw_item):
                    invalid_negative_count += 1
                continue
            infos.append(_ArticleInfo(article_id=article_id, rank=_extract_rank(raw_item, position), score=_extract_score(raw_item)))

    summary["invalid_negative_article_ids_count"] += invalid_negative_count
    return _dedupe_article_infos(infos)


def _extract_article_id(raw_item: Any, canonical_article_ids: set[str]) -> str | None:
    raw_article_id = _extract_raw_article_id(raw_item)
    if raw_article_id in canonical_article_ids:
        return raw_article_id
    return None


def _extract_raw_article_id(raw_item: Any) -> str | None:
    if isinstance(raw_item, str):
        value = raw_item.strip()
        return value or None

    if not isinstance(raw_item, dict):
        return None

    for field_name in ARTICLE_ID_FIELD_NAMES:
        value = raw_item.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()

    # Hit chunk-level chỉ được dùng khi metadata có parent/canonical article_id.
    for metadata_field_name in METADATA_FIELD_NAMES:
        metadata = raw_item.get(metadata_field_name)
        if isinstance(metadata, dict):
            nested_id = _extract_raw_article_id(metadata)
            if nested_id:
                return nested_id

    return None


def _extract_question_id(row: dict[str, Any], row_index: int) -> str:
    for field_name in ("question_id", "id"):
        value = row.get(field_name)
        if value is not None:
            return str(value)
    return str(row_index)


def _extract_query(row: dict[str, Any]) -> str:
    for field_name in ("query", "question"):
        value = row.get(field_name)
        if isinstance(value, str):
            return value
    return ""


def _extract_rank(raw_item: Any, fallback_rank: int) -> int | None:
    if not isinstance(raw_item, dict):
        return fallback_rank
    value = raw_item.get("rank")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return fallback_rank


def _extract_score(raw_item: Any) -> float | None:
    if not isinstance(raw_item, dict):
        return None
    for field_name in ("score", "final_score", "rerank_score", "rrf_score", "bm25_score", "dense_score"):
        value = raw_item.get(field_name)
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _record_no_positive_or_invalid(
    row: dict[str, Any],
    canonical_article_ids: set[str],
    summary: dict[str, Any],
) -> None:
    invalid_positive_ids = _extract_invalid_positive_article_ids(row, canonical_article_ids)
    if invalid_positive_ids:
        summary["questions_skipped_invalid_positive"] += 1
        _record_invalid_ids(invalid_positive_ids, summary["invalid_positive_article_ids"])
    else:
        summary["questions_skipped_no_positive"] += 1


def _record_invalid_ids(values: list[str], collector: set[str]) -> None:
    for value in values:
        collector.add(value)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _dedupe(values: Any) -> list[Any]:
    seen: set[Any] = set()
    result: list[Any] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dedupe_article_infos(values: list[_ArticleInfo]) -> list[_ArticleInfo]:
    seen: set[str] = set()
    result: list[_ArticleInfo] = []
    for value in values:
        if value.article_id in seen:
            continue
        seen.add(value.article_id)
        result.append(value)
    return result


def _new_summary(output_path: Path, summary_path: Path) -> dict[str, Any]:
    return {
        "total_questions_seen": 0,
        "samples_written": 0,
        "questions_skipped_no_positive": 0,
        "questions_skipped_invalid_positive": 0,
        "questions_skipped_no_hard_negatives": 0,
        "invalid_positive_article_ids": set(),
        "invalid_negative_article_ids_count": 0,
        "weak_label": True,
        "dataset_type": "weak_supervision",
        "label_source": "retrieval_selected_articles",
        "output_path": str(output_path),
        "summary_path": str(summary_path),
    }


def _validate_build_options(max_questions: int | None, max_hard_negatives: int) -> None:
    if max_questions is not None and max_questions < 1:
        raise ValueError("max_questions must be None or a positive integer")
    if max_hard_negatives < 1:
        raise ValueError("max_hard_negatives must be a positive integer")


def _ensure_can_write(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists, pass overwrite=True to replace: {path}")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build weak-supervision reranker training data.")
    parser.add_argument("--retrieval-results", type=Path, default=DEFAULT_RETRIEVAL_RESULTS_PATH)
    parser.add_argument("--legal-articles", type=Path, default=DEFAULT_LEGAL_ARTICLES_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--max-questions", type=int, default=None)
    parser.add_argument("--max-hard-negatives", type=int, default=5)
    parser.add_argument("--min-positive-score", type=float, default=None)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    args = _build_arg_parser().parse_args()
    summary = build_reranker_training_data(
        retrieval_results_path=args.retrieval_results,
        legal_articles_path=args.legal_articles,
        output_path=args.output,
        summary_path=args.summary,
        max_questions=args.max_questions,
        max_hard_negatives=args.max_hard_negatives,
        min_positive_score=args.min_positive_score,
        overwrite=args.overwrite,
    )
    LOGGER.info("Reranker weak-supervision data summary: %s", summary)


if __name__ == "__main__":
    main()
