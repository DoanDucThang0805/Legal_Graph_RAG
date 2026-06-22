"""Patch conservative legacy metadata display text in generated answers.

This module only edits the answer string for target IDs identified by P6.R7.
It does not change retrieval rows, selected articles, canonical metadata, or
submission fields.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

OUTPUT_ANSWERS_FILENAME = "generated_answers_p6r8_legacy_display_patch.jsonl"
PATCH_REPORT_FILENAME = "legacy_answer_patch_report.csv"
PATCH_SUMMARY_FILENAME = "legacy_answer_patch_summary.json"

TARGET_ACTION = "answer_patch_possible"
THINK_MARKERS = ("<think>", "</think>")
LEGAL_BASIS_MARKER = "C\u0103n c\u1ee9 ph\u00e1p l\u00fd"

REPORT_COLUMNS = [
    "id",
    "recommended_action",
    "patched",
    "before_contains_khong_so",
    "after_contains_khong_so",
    "before_answer_preview",
    "after_answer_preview",
    "patch_notes",
]

PREFIX_KHONG_SO_PATTERN = re.compile(
    r"\b(?P<prefix>Ph\u00e1p\s+l\u1ec7nh|Lu\u1eadt|B\u1ed9\s+lu\u1eadt)\s+(?:Kh\u00f4ng|Khong)\s+(?:s\u1ed1|so)\s+",
    flags=re.IGNORECASE,
)
SO_KHONG_SO_PATTERN = re.compile(
    r"\b(?:s\u1ed1|S\u1ed1|so|So)\s+(?:Kh\u00f4ng|kh\u00f4ng|Khong|khong)\s+(?:s\u1ed1|so)\b",
)


def run_legacy_answer_display_patch(
    p6r7_report_path: str | Path,
    answers_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Patch target answer display text and write JSONL, report CSV, and summary."""
    target_actions = read_target_actions(p6r7_report_path)
    answer_rows = read_jsonl_records(answers_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    target_ids = {row_id for row_id, action in target_actions.items() if action == TARGET_ACTION}
    patched_rows: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []
    changed_non_target_ids: list[str] = []
    ids_seen: set[str] = set()
    duplicate_ids: list[str] = []
    empty_answer_ids: list[str] = []
    think_marker_ids: list[str] = []
    legal_basis_lost_ids: list[str] = []

    for row in answer_rows:
        output_row = dict(row)
        row_id = _safe_text(row.get("id"))
        if row_id in ids_seen:
            duplicate_ids.append(row_id)
        ids_seen.add(row_id)

        before_answer = _safe_text(row.get("answer"))
        before_has_legal_basis = LEGAL_BASIS_MARKER in before_answer
        patched_answer = before_answer
        notes: list[str] = []
        if row_id in target_ids:
            patched_answer, notes = patch_legacy_answer_display(before_answer)
            output_row["answer"] = patched_answer

        if row_id not in target_ids and patched_answer != before_answer:
            changed_non_target_ids.append(row_id)
        if not _safe_text(output_row.get("answer")):
            empty_answer_ids.append(row_id)
        if any(marker in _safe_text(output_row.get("answer")) for marker in THINK_MARKERS):
            think_marker_ids.append(row_id)
        if before_has_legal_basis and LEGAL_BASIS_MARKER not in _safe_text(output_row.get("answer")):
            legal_basis_lost_ids.append(row_id)

        if row_id in target_ids:
            report_rows.append(
                {
                    "id": row_id,
                    "recommended_action": target_actions.get(row_id, ""),
                    "patched": patched_answer != before_answer,
                    "before_contains_khong_so": contains_khong_so(before_answer),
                    "after_contains_khong_so": contains_khong_so(patched_answer),
                    "before_answer_preview": preview(before_answer),
                    "after_answer_preview": preview(patched_answer),
                    "patch_notes": ";".join(notes) if notes else "unchanged_no_khong_so_pattern",
                }
            )
        patched_rows.append(output_row)

    output_answers_path = output_path / OUTPUT_ANSWERS_FILENAME
    report_path = output_path / PATCH_REPORT_FILENAME
    summary_path = output_path / PATCH_SUMMARY_FILENAME
    write_jsonl(output_answers_path, patched_rows)
    write_csv(report_path, REPORT_COLUMNS, report_rows)

    patched_count = sum(_as_bool(row.get("patched")) for row in report_rows)
    before_contains_count = sum(_as_bool(row.get("before_contains_khong_so")) for row in report_rows)
    after_contains_count = sum(_as_bool(row.get("after_contains_khong_so")) for row in report_rows)
    summary = {
        "input_answer_path": str(answers_path),
        "p6r7_report_path": str(p6r7_report_path),
        "output_answer_path": str(output_answers_path),
        "total_answers": len(answer_rows),
        "target_patch_ids": len(target_ids),
        "patched_count": patched_count,
        "before_contains_khong_so_count": before_contains_count,
        "after_contains_khong_so_count": after_contains_count,
        "unchanged_target_count": len(target_ids) - patched_count,
        "non_target_changed_count": len(changed_non_target_ids),
        "safety_checks": {
            "row_count_is_2000": len(answer_rows) == 2000,
            "unique_id_count": len(ids_seen),
            "unique_id_count_is_2000": len(ids_seen) == 2000,
            "duplicate_ids": duplicate_ids,
            "empty_answer_ids": empty_answer_ids,
            "non_target_changed_ids": changed_non_target_ids,
            "think_marker_ids": think_marker_ids,
            "legal_basis_lost_ids": legal_basis_lost_ids,
            "only_target_ids_changed": not changed_non_target_ids,
            "no_empty_answers": not empty_answer_ids,
            "no_think_markers": not think_marker_ids,
            "legal_basis_preserved": not legal_basis_lost_ids,
        },
    }
    write_json(summary_path, summary)
    return {**summary, "report_path": str(report_path), "summary_path": str(summary_path)}


def patch_legacy_answer_display(answer: str) -> tuple[str, list[str]]:
    """Remove only display-level 'Khong so' fragments, never infer law IDs."""
    text = str(answer or "")
    notes: list[str] = []
    patched, count_prefix = PREFIX_KHONG_SO_PATTERN.subn(lambda match: f"{match.group('prefix')} ", text)
    if count_prefix:
        notes.append("removed_prefix_khong_so")
    patched, count_so = SO_KHONG_SO_PATTERN.subn("", patched)
    if count_so:
        notes.append("removed_so_khong_so")
    if notes:
        patched = cleanup_spacing_preserve_lines(patched)
    return patched, notes


def cleanup_spacing_preserve_lines(text: str) -> str:
    """Clean spaces per line while preserving newline and bullet structure."""
    lines = str(text or "").splitlines()
    cleaned = []
    for line in lines:
        compact = re.sub(r"[ \t]{2,}", " ", line)
        compact = re.sub(r"\s+([,.;:!?])", r"\1", compact)
        compact = re.sub(r"([(\[])\s+", r"\1", compact)
        cleaned.append(compact.strip())
    result = "\n".join(cleaned)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def contains_khong_so(value: Any) -> bool:
    return "khong so" in ascii_fold(value)


def read_target_actions(path: str | Path) -> dict[str, str]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"P6.R7 report does not exist: {source}")
    actions: dict[str, str] = {}
    with source.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        required = {"id", "recommended_action"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"P6.R7 report missing required columns: {sorted(missing)}")
        for row in reader:
            row_id = _safe_text(row.get("id"))
            if row_id:
                actions[row_id] = _safe_text(row.get("recommended_action"))
    return actions


def read_jsonl_records(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"answers JSONL does not exist: {source}")
    rows: list[dict[str, Any]] = []
    with source.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            loaded = json.loads(line)
            if not isinstance(loaded, dict):
                raise ValueError(f"JSONL line {line_number} must be an object")
            rows.append(loaded)
    return rows


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, columns: list[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def preview(value: Any, limit: int = 240) -> str:
    text = " ".join(_safe_text(value).split())
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)] + "..."


def ascii_fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _safe_text(value)).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.casefold().split())


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _safe_text(value).casefold() in {"true", "1", "yes"}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
