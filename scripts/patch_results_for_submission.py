"""Deterministically patch a results.json candidate for safer submission."""

from __future__ import annotations

import argparse
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

LOGGER = logging.getLogger(__name__)

REQUIRED_FIELDS = {"id", "question", "answer", "relevant_docs", "relevant_articles"}

DISCLAIMER_PATTERNS = (
    r"LÆ°u\s+Ã½\s*:?\s*Ä‘Ã¢y\s+lÃ \s+thÃ´ng\s+tin\s+tham\s+kháº£o\s+dá»±a\s+trÃªn\s+cÄƒn\s+cá»©\s+Ä‘Æ°á»£c\s+cung\s+cáº¥p\.?",
    r"ÄÃ¢y\s+lÃ \s+thÃ´ng\s+tin\s+tham\s+kháº£o\s+dá»±a\s+trÃªn\s+cÄƒn\s+cá»©\s+Ä‘Æ°á»£c\s+cung\s+cáº¥p\.?",
)
INTERNAL_LEAKAGE_PATTERNS = (
    r"Theo\s+thÃ´ng\s+tin\s+Ä‘Æ°á»£c\s+cung\s+cáº¥p\s+trong\s+selected_articles/context,?\s*",
    r"trong\s+selected_articles/context",
    r"selected_articles/context",
)


@dataclass
class PatchOptions:
    remove_disclaimer: bool = True
    remove_internal_leakage: bool = True
    remove_khong_so_refs: bool = True
    deduplicate_refs: bool = True
    enable_prune: bool = False
    max_articles: int = 6
    max_docs: int = 5
    fail_if_empty_refs: bool = True


@dataclass
class PatchStats:
    total_records: int = 0
    records_changed: int = 0
    answers_changed: int = 0
    refs_changed: int = 0
    disclaimers_removed: int = 0
    internal_leakage_removed: int = 0
    khong_so_refs_removed: int = 0
    duplicate_docs_removed: int = 0
    duplicate_articles_removed: int = 0
    pruned_articles_count: int = 0
    pruned_docs_count: int = 0
    rollback_count: int = 0
    warnings_count: int = 0


@dataclass
class RecordChange:
    id: int
    changed_fields: list[str] = field(default_factory=list)
    before_counts: dict[str, int] = field(default_factory=dict)
    after_counts: dict[str, int] = field(default_factory=dict)
    removed_docs: list[str] = field(default_factory=list)
    removed_articles: list[str] = field(default_factory=list)
    answer_changed: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "changed_fields": self.changed_fields,
            "before_counts": self.before_counts,
            "after_counts": self.after_counts,
            "removed_docs": self.removed_docs,
            "removed_articles": self.removed_articles,
            "answer_changed": self.answer_changed,
            "warnings": self.warnings,
        }


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    options = PatchOptions(
        remove_disclaimer=args.remove_disclaimer,
        remove_internal_leakage=args.remove_internal_leakage,
        remove_khong_so_refs=args.remove_khong_so_refs,
        deduplicate_refs=args.deduplicate_refs,
        enable_prune=args.enable_prune,
        max_articles=args.max_articles,
        max_docs=args.max_docs,
        fail_if_empty_refs=args.fail_if_empty_refs,
    )

    try:
        items = load_results(args.input)
        patched_items, report, changes = patch_results_items(
            items,
            options=options,
            input_path=Path(args.input),
            output_path=Path(args.output),
        )
    except PatchError as exc:
        LOGGER.error("%s", exc)
        return 1

    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    write_json(args.output, patched_items)
    write_json(args.report, report)
    write_changes(args.changes, changes)
    if args.zip_output:
        write_flat_zip(args.output, args.zip_output)
    LOGGER.info("Wrote patched results to %s", args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safely patch a submission results.json candidate.")
    parser.add_argument("--input", default="data/outputs/results.json")
    parser.add_argument("--output", default="data/outputs/results_patched_safe.json")
    parser.add_argument("--report", default="data/outputs/results_patch_report.json")
    parser.add_argument("--changes", default="data/outputs/results_patch_changes.jsonl")
    parser.add_argument("--remove-disclaimer", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--remove-internal-leakage", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--remove-khong-so-refs", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--deduplicate-refs", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--enable-prune", action="store_true", default=False)
    parser.add_argument("--max-articles", type=positive_int, default=6)
    parser.add_argument("--max-docs", type=positive_int, default=5)
    parser.add_argument("--fail-if-empty-refs", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dry-run", action="store_true", help="Print report only; do not write outputs.")
    parser.add_argument("--zip-output", default=None, help="Optional flat zip output path.")
    parser.add_argument("--log-level", default="INFO")
    return parser


def load_results(path: str | Path) -> list[dict[str, Any]]:
    source_path = Path(path)
    try:
        loaded = json.loads(source_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PatchError(f"input file not found: {source_path}") from exc
    except json.JSONDecodeError as exc:
        raise PatchError(f"input file is not valid JSON: {exc}") from exc

    validate_schema(loaded)
    return loaded


def validate_schema(items: Any) -> None:
    if not isinstance(items, list):
        raise PatchError("results root must be a list")

    seen_ids: set[int] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise PatchError(f"item {index} must be an object")

        missing = sorted(REQUIRED_FIELDS.difference(item))
        if missing:
            raise PatchError(f"item {index} missing required field(s): {missing}")

        item_id = item.get("id")
        if not isinstance(item_id, int):
            raise PatchError(f"item {index} id must be an integer")
        if item_id in seen_ids:
            raise PatchError(f"duplicate id: {item_id}")
        seen_ids.add(item_id)

        if not isinstance(item.get("question"), str):
            raise PatchError(f"item {index} question must be a string")
        if not isinstance(item.get("answer"), str):
            raise PatchError(f"item {index} answer must be a string")
        if not is_string_list(item.get("relevant_docs")):
            raise PatchError(f"item {index} relevant_docs must be a list of strings")
        if not is_string_list(item.get("relevant_articles")):
            raise PatchError(f"item {index} relevant_articles must be a list of strings")


def patch_results_items(
    items: list[dict[str, Any]],
    *,
    options: PatchOptions,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    validate_schema(items)
    stats = PatchStats(total_records=len(items))
    patched_items: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []

    for item in items:
        patched_item, change = patch_record(item, options=options, stats=stats)
        patched_items.append(patched_item)
        changes.append(change.to_json())

    validate_output_invariants(items, patched_items, options)
    stats.records_changed = sum(1 for change in changes if change["changed_fields"])
    stats.warnings_count = sum(len(change["warnings"]) for change in changes)
    report = build_report(
        stats,
        output_records=len(patched_items),
        input_path=input_path,
        output_path=output_path,
    )
    return patched_items, report, changes


def patch_record(item: dict[str, Any], *, options: PatchOptions, stats: PatchStats) -> tuple[dict[str, Any], RecordChange]:
    original_answer = item["answer"]
    original_docs = list(item["relevant_docs"])
    original_articles = list(item["relevant_articles"])
    patched = dict(item)
    change = RecordChange(
        id=item["id"],
        before_counts={"relevant_docs": len(original_docs), "relevant_articles": len(original_articles)},
    )

    answer, disclaimer_count, leakage_count = patch_answer(original_answer, options)
    if not answer.strip():
        answer = original_answer
        change.warnings.append("answer patch would make answer empty; rolled back answer")
        stats.rollback_count += 1
    patched["answer"] = answer
    if answer != original_answer:
        change.answer_changed = True
        change.changed_fields.append("answer")
        stats.answers_changed += 1
    stats.disclaimers_removed += disclaimer_count
    stats.internal_leakage_removed += leakage_count

    docs, articles, ref_warnings, ref_counters = patch_references(
        original_docs,
        original_articles,
        options=options,
    )
    if ref_warnings:
        change.warnings.extend(ref_warnings)
        stats.rollback_count += sum(1 for warning in ref_warnings if "rolled back" in warning)

    patched["relevant_docs"] = docs
    patched["relevant_articles"] = articles
    if docs != original_docs:
        change.changed_fields.append("relevant_docs")
    if articles != original_articles:
        change.changed_fields.append("relevant_articles")
    if docs != original_docs or articles != original_articles:
        stats.refs_changed += 1

    stats.khong_so_refs_removed += ref_counters["khong_so_refs_removed"]
    stats.duplicate_docs_removed += ref_counters["duplicate_docs_removed"]
    stats.duplicate_articles_removed += ref_counters["duplicate_articles_removed"]
    stats.pruned_articles_count += ref_counters["pruned_articles_count"]
    stats.pruned_docs_count += ref_counters["pruned_docs_count"]

    change.removed_docs = [doc for doc in original_docs if doc not in docs]
    change.removed_articles = [article for article in original_articles if article not in articles]
    change.after_counts = {"relevant_docs": len(docs), "relevant_articles": len(articles)}
    return patched, change


def patch_answer(answer: str, options: PatchOptions) -> tuple[str, int, int]:
    patched = answer
    disclaimer_count = 0
    leakage_count = 0

    if options.remove_disclaimer:
        patched, inline_disclaimer_count = remove_inline_disclaimer_suffixes(patched)
        patched, pattern_disclaimer_count = remove_patterns(patched, DISCLAIMER_PATTERNS)
        patched, line_disclaimer_count = remove_disclaimer_lines(patched)
        disclaimer_count += inline_disclaimer_count + pattern_disclaimer_count + line_disclaimer_count
    if options.remove_internal_leakage:
        patched, leakage_count = remove_patterns(patched, INTERNAL_LEAKAGE_PATTERNS)
    return normalize_answer_spacing(patched), disclaimer_count, leakage_count


def remove_patterns(text: str, patterns: Sequence[str]) -> tuple[str, int]:
    patched = text
    total = 0
    for pattern in patterns:
        patched, count = re.subn(pattern, "", patched, flags=re.IGNORECASE)
        total += count
    return patched, total



def remove_inline_disclaimer_suffixes(text: str) -> tuple[str, int]:
    lines: list[str] = []
    removed_count = 0
    for line in text.splitlines():
        prefix = find_inline_disclaimer_prefix(line)
        if prefix is None:
            lines.append(line)
            continue
        lines.append(line[:prefix].rstrip())
        removed_count += 1
    return "\n".join(lines), removed_count

def remove_disclaimer_lines(text: str) -> tuple[str, int]:
    """Remove residual disclaimer lines without touching legal analysis lines."""

    kept_lines: list[str] = []
    removed_count = 0
    for line in text.splitlines():
        if is_disclaimer_line(line):
            removed_count += 1
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines), removed_count


def find_inline_disclaimer_prefix(line: str) -> int | None:
    markers = (
        "Lưu ý:",
        "Lưu ý",
        "LÆ°u Ã½:",
        "LÆ°u Ã½",
        "Thông tin tham khảo",
        "ThÃ´ng tin tham kháº£o",
        "Đây là thông tin tham khảo",
        "ÄÃ¢y lÃ  thÃ´ng tin tham kháº£o",
    )
    for marker in markers:
        index = line.find(marker)
        if index < 0:
            continue
        suffix = line[index:]
        if is_disclaimer_line(suffix):
            return index
    return None

def is_disclaimer_line(line: str) -> bool:
    normalized = normalize_for_matching(line)
    if "thong tin tham khao" not in normalized:
        return False

    disclaimer_prefixes = (
        "thong tin tham khao",
        "luu y thong tin tham khao",
        "luu y: thong tin tham khao",
        "luu y day la thong tin tham khao",
        "luu y: day la thong tin tham khao",
        "day la thong tin tham khao",
    )
    return normalized.startswith(disclaimer_prefixes)

def patch_references(
    docs: list[str],
    articles: list[str],
    *,
    options: PatchOptions,
) -> tuple[list[str], list[str], list[str], dict[str, int]]:
    warnings: list[str] = []
    counters = {
        "khong_so_refs_removed": 0,
        "duplicate_docs_removed": 0,
        "duplicate_articles_removed": 0,
        "pruned_articles_count": 0,
        "pruned_docs_count": 0,
    }
    patched_docs = list(docs)
    patched_articles = list(articles)

    if options.deduplicate_refs:
        before_docs = len(patched_docs)
        before_articles = len(patched_articles)
        patched_docs = deduplicate_preserve_order(patched_docs)
        patched_articles = deduplicate_preserve_order(patched_articles)
        counters["duplicate_docs_removed"] += before_docs - len(patched_docs)
        counters["duplicate_articles_removed"] += before_articles - len(patched_articles)

    if options.remove_khong_so_refs:
        before_docs = list(patched_docs)
        before_articles = list(patched_articles)
        patched_docs = [doc for doc in patched_docs if not contains_khong_so(doc)]
        patched_articles = [article for article in patched_articles if not contains_khong_so(article)]
        removed_count = (len(before_docs) - len(patched_docs)) + (len(before_articles) - len(patched_articles))
        counters["khong_so_refs_removed"] += removed_count

        if not patched_articles:
            patched_docs = before_docs
            patched_articles = before_articles
            counters["khong_so_refs_removed"] -= removed_count
            warnings.append("removing Khong so refs would empty relevant_articles; rolled back refs")
        elif not patched_docs:
            patched_docs = docs_from_articles(patched_articles)
            if not patched_docs:
                patched_docs = before_docs
                patched_articles = before_articles
                counters["khong_so_refs_removed"] -= removed_count
                warnings.append("removing Khong so refs would empty relevant_docs; rolled back refs")

    patched_docs = sync_docs_to_articles(patched_docs, patched_articles)

    if options.enable_prune:
        before_articles = list(patched_articles)
        before_docs = list(patched_docs)
        if len(patched_articles) > options.max_articles:
            patched_articles = patched_articles[: options.max_articles]
            counters["pruned_articles_count"] += len(before_articles) - len(patched_articles)
        patched_docs = sync_docs_to_articles(patched_docs, patched_articles)
        if len(patched_docs) > options.max_docs:
            patched_docs = patched_docs[: options.max_docs]
            counters["pruned_docs_count"] += len(before_docs) - len(patched_docs)
        if not patched_articles:
            patched_docs = before_docs
            patched_articles = before_articles
            counters["pruned_articles_count"] = 0
            counters["pruned_docs_count"] = 0
            warnings.append("pruning would empty relevant_articles; rolled back refs")

    if options.fail_if_empty_refs and (not patched_docs or not patched_articles):
        raise PatchError("patch would produce empty relevant_docs or relevant_articles")
    return patched_docs, patched_articles, warnings, counters


def sync_docs_to_articles(docs: list[str], articles: list[str]) -> list[str]:
    article_docs = docs_from_articles(articles)
    if not article_docs:
        return docs

    allowed = set(article_docs)
    synced = [doc for doc in docs if doc in allowed]
    if synced:
        return synced
    return article_docs


def docs_from_articles(articles: list[str]) -> list[str]:
    docs: list[str] = []
    seen: set[str] = set()
    for article in articles:
        parsed = parse_article_ref(article)
        if parsed is None:
            continue
        law_id, law_title, _ = parsed
        doc = f"{law_id}|{law_title}"
        if doc not in seen:
            seen.add(doc)
            docs.append(doc)
    return docs


def parse_article_ref(value: str) -> tuple[str, str, str] | None:
    parts = [part.strip() for part in str(value or "").split("|", maxsplit=2)]
    if len(parts) != 3 or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


def deduplicate_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result



def normalize_for_matching(value: str) -> str:
    normalized = repair_common_mojibake(str(value or ""))
    return re.sub(r"\s+", " ", strip_accents(normalized).casefold()).strip()


def repair_common_mojibake(value: str) -> str:
    replacements = {
        "KhÃ´ng sá»‘": "Không số",
        "khÃ´ng sá»‘": "không số",
        "LÆ°u Ã½": "Lưu ý",
        "lÆ°u Ã½": "lưu ý",
        "ThÃ´ng tin tham kháº£o": "Thông tin tham khảo",
        "thÃ´ng tin tham kháº£o": "thông tin tham khảo",
        "ÄÃ¢y lÃ ": "Đây là",
        "Ä‘Ã¢y lÃ ": "đây là",
        "dá»±a trÃªn": "dựa trên",
        "cÄƒn cá»©": "căn cứ",
        "Ä‘Æ°á»£c": "được",
        "cung cáº¥p": "cung cấp",
    }
    repaired = value
    for old, new in replacements.items():
        repaired = repaired.replace(old, new)
    return repaired


def contains_khong_so(value: str) -> bool:
    normalized = normalize_for_matching(str(value))
    return "khong so" in normalized


def strip_accents(value: str) -> str:
    normalized = str(value or "").replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", normalized)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")

def normalize_answer_spacing(value: str) -> str:
    patched = re.sub(r"[ \t]+", " ", value)
    patched = re.sub(r"\s+([,.;:])", r"\1", patched)
    patched = re.sub(r"\n{3,}", "\n\n", patched)
    return patched.strip()


def validate_output_invariants(
    original_items: list[dict[str, Any]],
    patched_items: list[dict[str, Any]],
    options: PatchOptions,
) -> None:
    if len(original_items) != len(patched_items):
        raise PatchError("patched output changed record count")

    for index, (original, patched) in enumerate(zip(original_items, patched_items, strict=True)):
        if original["id"] != patched.get("id"):
            raise PatchError(f"item {index} id changed")
        if original["question"] != patched.get("question"):
            raise PatchError(f"item {index} question changed")
        if not str(patched.get("answer", "")).strip():
            raise PatchError(f"item {index} answer is empty after patch")
        if options.fail_if_empty_refs and (not patched.get("relevant_docs") or not patched.get("relevant_articles")):
            raise PatchError(f"item {index} refs are empty after patch")


def build_report(
    stats: PatchStats,
    *,
    output_records: int,
    input_path: Path | None,
    output_path: Path | None,
) -> dict[str, Any]:
    return {
        "total_records": stats.total_records,
        "records_changed": stats.records_changed,
        "answers_changed": stats.answers_changed,
        "refs_changed": stats.refs_changed,
        "disclaimers_removed": stats.disclaimers_removed,
        "internal_leakage_removed": stats.internal_leakage_removed,
        "khong_so_refs_removed": stats.khong_so_refs_removed,
        "duplicate_docs_removed": stats.duplicate_docs_removed,
        "duplicate_articles_removed": stats.duplicate_articles_removed,
        "pruned_articles_count": stats.pruned_articles_count,
        "pruned_docs_count": stats.pruned_docs_count,
        "rollback_count": stats.rollback_count,
        "warnings_count": stats.warnings_count,
        "output_records": output_records,
        "input_path": str(input_path) if input_path is not None else None,
        "output_path": str(output_path) if output_path is not None else None,
    }


def write_json(path: str | Path, value: Any) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_changes(path: str | Path, changes: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for change in changes:
            file.write(json.dumps(change, ensure_ascii=False, sort_keys=True))
            file.write("\n")


def write_flat_zip(results_path: str | Path, zip_path: str | Path) -> Path:
    source_path = Path(results_path)
    output_path = Path(zip_path)
    if not source_path.is_file():
        raise PatchError(f"results file does not exist for zip: {source_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.write(source_path, arcname="results.json")
    return output_path


def is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


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


class PatchError(RuntimeError):
    """User-facing patch failure."""


if __name__ == "__main__":
    raise SystemExit(main())






