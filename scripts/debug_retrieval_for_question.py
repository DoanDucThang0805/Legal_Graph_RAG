"""Inspect retrieval artifacts for one question without generating answers."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Sequence

LOGGER = logging.getLogger(__name__)

DEFAULT_ANALYZED_QUESTIONS = Path("data/processed/test_questions_analyzed.parquet")
DEFAULT_QUESTIONS = Path("data/processed/test_questions.parquet")
DEFAULT_RETRIEVAL_FILE = Path("data/outputs/retrieval_results.jsonl")

ID_FIELDS = ("id", "question_id")
QUESTION_FIELDS = ("question", "question_text")
BM25_FIELDS = ("bm25_hits", "bm25", "lexical_hits", "legal_bm25_hits")
DENSE_FIELDS = ("dense_hits", "vector_hits", "dense", "legal_dense_hits")
EXACT_FIELDS = ("exact_hits", "exact")
PHAPDIEN_FIELDS = ("phapdien_hits", "phapdien_mapped_hits", "phapdien")
MERGED_FIELDS = ("merged_candidates", "rrf_candidates", "candidates")
SELECTED_FIELDS = ("selected_articles", "selected_article_ids", "final_articles")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    repo_root = Path(args.cwd).expanduser().resolve()
    warnings: list[str] = []

    try:
        if args.live:
            record, question_record = run_live_debug(args, repo_root, warnings)
        else:
            record, question_record = run_offline_debug(args, repo_root, warnings)
    except DebugInputError as exc:
        print(f"[ERROR] {exc}")
        return 1

    debug_payload = build_debug_payload(
        question_id=args.id,
        record=record,
        question_record=question_record,
        warnings=warnings,
        top_k=args.top_k,
        show_text=args.show_text,
        max_text_chars=args.max_text_chars,
    )

    if args.json_output:
        print(json.dumps(debug_payload, ensure_ascii=False, indent=2))
    else:
        print(format_debug_payload(debug_payload))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Debug retrieval artifacts for one question id.")
    parser.add_argument("--id", type=int, required=True, help="Question id to inspect.")
    parser.add_argument("--top-k", type=positive_int, default=10, help="Number of hits to show per section.")
    parser.add_argument("--retrieval-file", default=None, help="Path to retrieval_results JSONL.")
    parser.add_argument(
        "--use-current-retrieval-file",
        action="store_true",
        help="Use an existing retrieval JSONL file and do not call retrieval services.",
    )
    parser.add_argument(
        "--questions-file",
        default=None,
        help="Question parquet/csv file. Defaults to analyzed parquet, then raw processed questions parquet.",
    )
    parser.add_argument("--show-text", action="store_true", help="Show snippet/text fields for hits.")
    parser.add_argument("--max-text-chars", type=positive_int, default=500)
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON instead of pretty text.")
    parser.add_argument("--no-color", action="store_true", help="Accepted for CLI compatibility; output is plain text.")
    parser.add_argument("--cwd", default=".", help="Repository root for relative input paths.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run HybridLegalRetriever for this question. Offline mode is the default and safer.",
    )
    parser.add_argument("--log-level", default="INFO")
    return parser


def run_offline_debug(
    args: argparse.Namespace,
    repo_root: Path,
    warnings: list[str],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    retrieval_path = resolve_path(
        args.retrieval_file if args.retrieval_file else DEFAULT_RETRIEVAL_FILE,
        repo_root,
    )
    if not retrieval_path.exists():
        raise DebugInputError(
            f"Retrieval file not found: {retrieval_path}. "
            "Pass --retrieval-file or run with --live explicitly if you want service-backed retrieval."
        )

    record, retrieval_warnings = load_retrieval_record_by_id(retrieval_path, args.id)
    warnings.extend(retrieval_warnings)
    if record is None:
        raise DebugInputError(f"Question id={args.id} not found in retrieval file: {retrieval_path}")

    question_record = load_question_by_id(resolve_questions_path(args.questions_file, repo_root), args.id, warnings)
    return record, question_record


def run_live_debug(
    args: argparse.Namespace,
    repo_root: Path,
    warnings: list[str],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    question_record = load_question_by_id(resolve_questions_path(args.questions_file, repo_root), args.id, warnings)
    if question_record is None:
        raise DebugInputError(f"Question id={args.id} not found in question file.")

    question = first_present(question_record, QUESTION_FIELDS)
    if not question:
        raise DebugInputError(f"Question id={args.id} has no question text.")

    try:
        from backend.retrieval.hybrid_retrieval import HybridLegalRetriever
    except Exception as exc:
        raise DebugInputError(f"Could not import HybridLegalRetriever: {exc}") from exc

    try:
        result = HybridLegalRetriever().retrieve(
            {
                "question": question,
                "answer_type": question_record.get("answer_type"),
                "complexity": question_record.get("complexity"),
            },
            top_k=args.top_k,
        )
    except Exception as exc:
        raise DebugInputError(
            "Live retrieval failed. Check OpenSearch/Qdrant/index availability, "
            f"or use --retrieval-file for offline inspection. Root error: {exc}"
        ) from exc

    record = {
        "id": args.id,
        "question": question,
        "domain": question_record.get("domain"),
        "answer_type": question_record.get("answer_type"),
        "complexity": question_record.get("complexity"),
        "merged_candidates": [object_to_dict(candidate) for candidate in result.candidates],
        "selected_articles": list(result.selected_article_ids),
        "debug": result.debug,
    }
    warnings.append("Live mode uses existing HybridLegalRetriever; it does not generate answers.")
    return record, question_record


def load_question_by_id(path: Path | None, question_id: int, warnings: list[str] | None = None) -> dict[str, Any] | None:
    warnings = warnings if warnings is not None else []
    if path is None:
        warnings.append("Question file not found; only retrieval record fields will be shown.")
        return None
    if not path.exists():
        warnings.append(f"Question file not found: {path}")
        return None

    try:
        if path.suffix.lower() == ".csv":
            import polars as pl

            df = pl.read_csv(path)
        else:
            import polars as pl

            df = pl.read_parquet(path)
    except Exception as exc:
        warnings.append(f"Could not read question file {path}: {exc}")
        return None

    id_column = next((column for column in ID_FIELDS if column in df.columns), None)
    if id_column is None:
        warnings.append(f"Question file has no id column: {path}")
        return None

    for row in df.iter_rows(named=True):
        if ids_match(row.get(id_column), question_id):
            return dict(row)
    warnings.append(f"Question id={question_id} not found in question file: {path}")
    return None


def load_retrieval_record_by_id(path: Path, question_id: int) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    found: dict[str, Any] | None = None
    duplicate_count = 0

    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                loaded = json.loads(stripped)
            except json.JSONDecodeError as exc:
                warnings.append(f"Skip invalid JSONL line {line_number}: {exc}")
                continue
            if not isinstance(loaded, dict):
                warnings.append(f"Skip non-object JSONL line {line_number}")
                continue

            record_id = first_present(loaded, ID_FIELDS)
            if ids_match(record_id, question_id):
                if found is None:
                    found = loaded
                else:
                    duplicate_count += 1

    if duplicate_count:
        warnings.append(f"Found {duplicate_count + 1} records for id={question_id}; using the first record.")
    return found, warnings


def build_debug_payload(
    *,
    question_id: int,
    record: dict[str, Any],
    question_record: dict[str, Any] | None,
    warnings: list[str],
    top_k: int,
    show_text: bool,
    max_text_chars: int,
) -> dict[str, Any]:
    question = first_present(record, QUESTION_FIELDS) or first_present(question_record or {}, QUESTION_FIELDS)
    analysis_source = {**(question_record or {}), **record}
    debug = record.get("debug") if isinstance(record.get("debug"), dict) else {}

    return {
        "question": {
            "id": question_id,
            "text": question,
        },
        "analysis": {
            "domain": first_present(analysis_source, ("domain",)),
            "answer_type": first_present(analysis_source, ("answer_type",)),
            "complexity": first_present(analysis_source, ("complexity",)),
            "stage_counts": debug.get("stage_counts", {}),
            "errors": debug.get("errors", {}),
        },
        "bm25_hits": normalize_hit_group(first_present(record, BM25_FIELDS), top_k, show_text, max_text_chars),
        "dense_hits": normalize_hit_group(first_present(record, DENSE_FIELDS), top_k, show_text, max_text_chars),
        "exact_hits": normalize_hit_group(first_present(record, EXACT_FIELDS), top_k, show_text, max_text_chars),
        "phapdien_hits": normalize_hit_group(first_present(record, PHAPDIEN_FIELDS), top_k, show_text, max_text_chars),
        "rrf_merged": normalize_hit_group(first_present(record, MERGED_FIELDS), top_k, show_text, max_text_chars),
        "selected_articles": normalize_hit_group(first_present(record, SELECTED_FIELDS), top_k, show_text, max_text_chars),
        "warnings": warnings,
    }


def normalize_hit_group(value: Any, top_k: int, show_text: bool, max_text_chars: int) -> list[dict[str, Any]]:
    hits = ensure_list(value)
    normalized: list[dict[str, Any]] = []
    for index, hit in enumerate(hits[:top_k], start=1):
        item = normalize_hit(hit, rank=index)
        if show_text:
            text = item.get("text") or item.get("snippet") or item.get("article_text")
            if text:
                item["text"] = truncate_text(str(text), max_text_chars)
        else:
            item.pop("text", None)
            item.pop("snippet", None)
            item.pop("article_text", None)
        normalized.append(item)
    return normalized


def normalize_hit(hit: Any, *, rank: int) -> dict[str, Any]:
    if isinstance(hit, str):
        return {"rank": rank, "article_id": hit}
    if not isinstance(hit, dict):
        hit = object_to_dict(hit)

    metadata = hit.get("metadata") if isinstance(hit.get("metadata"), dict) else {}
    row = {"rank": hit.get("rank", rank)}
    for key in (
        "article_id",
        "legal_article_id",
        "law_id",
        "law_title",
        "article_no",
        "score",
        "final_score",
        "source",
        "retriever",
        "text",
        "snippet",
        "article_text",
        "phapdien_id",
        "mapping_score",
        "retrieval_score",
    ):
        value = hit.get(key)
        if value not in (None, ""):
            row[key] = value

    for key in ("law_id", "law_title", "article_no", "phapdien_id", "mapping_score", "retrieval_source"):
        value = metadata.get(key)
        if value not in (None, "") and key not in row:
            row[key] = value

    return row


def format_debug_payload(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    question = payload["question"]
    analysis = payload["analysis"]

    lines.extend(
        [
            "[QUESTION]",
            f"id: {question.get('id')}",
            f"text: {question.get('text') or '<missing>'}",
            "",
            "[ANALYSIS]",
            f"domain: {analysis.get('domain') or '<missing>'}",
            f"answer_type: {analysis.get('answer_type') or '<missing>'}",
            f"complexity: {analysis.get('complexity') or '<missing>'}",
            f"stage_counts: {analysis.get('stage_counts') or {}}",
            f"errors: {analysis.get('errors') or {}}",
            "",
        ]
    )

    section_map = (
        ("[BM25 HITS]", "bm25_hits"),
        ("[DENSE HITS]", "dense_hits"),
        ("[EXACT HITS]", "exact_hits"),
        ("[PHAPDIEN HITS]", "phapdien_hits"),
        ("[RRF MERGED]", "rrf_merged"),
        ("[SELECTED ARTICLES]", "selected_articles"),
    )
    for title, key in section_map:
        lines.append(title)
        lines.extend(format_hit_group(payload.get(key, [])))
        lines.append("")

    lines.append("[WARNINGS]")
    warning_lines = payload.get("warnings") or []
    if warning_lines:
        lines.extend(f"- {warning}" for warning in warning_lines)
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def format_hit_group(hits: list[dict[str, Any]]) -> list[str]:
    if not hits:
        return ["- none"]

    lines: list[str] = []
    for hit in hits:
        parts = [f"#{hit.get('rank')}"]
        for key in ("article_id", "legal_article_id", "law_id", "article_no", "score", "final_score", "source"):
            value = hit.get(key)
            if value not in (None, ""):
                parts.append(f"{key}={value}")
        lines.append("- " + " | ".join(parts))

        law_title = hit.get("law_title")
        if law_title:
            lines.append(f"  law_title: {law_title}")
        text = hit.get("text") or hit.get("snippet") or hit.get("article_text")
        if text:
            lines.append(f"  text: {text}")
    return lines


def resolve_questions_path(value: str | None, repo_root: Path) -> Path | None:
    if value:
        return resolve_path(value, repo_root)

    analyzed = resolve_path(DEFAULT_ANALYZED_QUESTIONS, repo_root)
    if analyzed.exists():
        return analyzed

    questions = resolve_path(DEFAULT_QUESTIONS, repo_root)
    if questions.exists():
        return questions
    return analyzed


def resolve_path(value: str | Path, repo_root: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return repo_root / path


def first_present(mapping: dict[str, Any], field_names: Sequence[str]) -> Any:
    for field_name in field_names:
        value = mapping.get(field_name)
        if value not in (None, ""):
            return value
    return None


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def ids_match(value: Any, question_id: int) -> bool:
    try:
        return int(value) == int(question_id)
    except (TypeError, ValueError):
        return str(value).strip() == str(question_id)


def truncate_text(text: str, max_chars: int) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= max_chars:
        return normalized
    if max_chars <= 3:
        return normalized[:max_chars]
    return normalized[: max_chars - 3].rstrip() + "..."


def object_to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {"value": str(value)}


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(levelname)s:%(name)s:%(message)s",
    )


class DebugInputError(RuntimeError):
    """Raised for user-facing debug input problems."""


if __name__ == "__main__":
    raise SystemExit(main())
