"""Merge regenerated QA subset answers into a copy of a generated answer JSONL."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def merge_generated_answer_subset(
    base_path: str | Path,
    subset_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Replace base answer rows by matching subset rows and preserve base row count."""
    base_records = _read_jsonl_records(Path(base_path), label="base")
    subset_records = _read_jsonl_records(Path(subset_path), label="subset")
    if not base_records:
        raise ValueError("base generated answer JSONL must not be empty")
    if not subset_records:
        raise ValueError("subset generated answer JSONL must not be empty")

    subset_by_id: dict[str, dict[str, Any]] = {}
    duplicate_subset_ids: set[str] = set()
    for record in subset_records:
        record_id = _required_id(record, label="subset")
        if record_id in subset_by_id:
            duplicate_subset_ids.add(record_id)
        subset_by_id[record_id] = record

    base_ids = {_required_id(record, label="base") for record in base_records}
    extra_subset_ids = sorted(record_id for record_id in subset_by_id if record_id not in base_ids)
    if extra_subset_ids:
        raise ValueError(f"subset contains IDs not present in base JSONL: {extra_subset_ids[:10]}")

    replaced_count = 0
    merged_records: list[dict[str, Any]] = []
    for record in base_records:
        record_id = _required_id(record, label="base")
        replacement = subset_by_id.get(record_id)
        if replacement is None:
            merged_records.append(record)
            continue
        merged_records.append(replacement)
        replaced_count += 1

    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8") as file:
        for record in merged_records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    if duplicate_subset_ids:
        logger.warning("Subset had duplicate IDs; last row won for %d IDs", len(duplicate_subset_ids))

    return {
        "base_rows": len(base_records),
        "subset_rows": len(subset_records),
        "output_rows": len(merged_records),
        "replaced": replaced_count,
        "duplicate_subset_ids": sorted(duplicate_subset_ids),
        "output_path": str(target_path),
    }


def _read_jsonl_records(path: Path, label: str) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} JSONL does not exist: {path}")

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid {label} JSONL at line {line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{label} JSONL line {line_number} must be an object")
            _required_id(value, label=f"{label} line {line_number}")
            records.append(value)
    return records


def _required_id(record: dict[str, Any], label: str) -> str:
    record_id = str(record.get("id") or "").strip()
    if not record_id:
        raise ValueError(f"{label} record missing id")
    return record_id
