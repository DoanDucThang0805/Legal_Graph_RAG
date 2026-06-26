"""Standalone schema and hygiene validator for submission JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

REQUIRED_FIELDS = {"id", "question", "answer", "relevant_docs", "relevant_articles"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate submission JSON schema and common hygiene flags.")
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)

    try:
        summary = validate_submission(args.input)
    except ValueError as exc:
        print(f"schema error: {exc}")
        return 1

    for key in (
        "records",
        "unique_ids",
        "empty_answer",
        "empty_docs",
        "empty_articles",
        "khong_so_refs_records",
        "disclaimer_records",
        "internal_leakage_records",
    ):
        print(f"{key}: {summary[key]}")
    print("schema ok")
    return 0


def validate_submission(path: str | Path) -> dict[str, int]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("root must be a list")

    ids: list[int] = []
    empty_answer = 0
    empty_docs = 0
    empty_articles = 0
    khong_so_refs = 0
    disclaimer_records = 0
    internal_leakage_records = 0

    for index, row in enumerate(data):
        if not isinstance(row, dict):
            raise ValueError(f"item {index} must be object")
        missing = REQUIRED_FIELDS.difference(row)
        if missing:
            raise ValueError(f"item {index} missing fields: {sorted(missing)}")
        if not isinstance(row["id"], int):
            raise ValueError(f"item {index} id must be int")
        if not isinstance(row["question"], str) or not isinstance(row["answer"], str):
            raise ValueError(f"item {index} question/answer must be strings")
        if not is_string_list(row["relevant_docs"]) or not is_string_list(row["relevant_articles"]):
            raise ValueError(f"item {index} refs must be string lists")

        ids.append(row["id"])
        empty_answer += int(not row["answer"].strip())
        empty_docs += int(not row["relevant_docs"])
        empty_articles += int(not row["relevant_articles"])
        refs_text = "\n".join(row["relevant_docs"] + row["relevant_articles"]).casefold()
        answer_text = row["answer"].casefold()
        khong_so_refs += int("không số" in refs_text or "khong so" in refs_text)
        disclaimer_records += int("thông tin tham khảo" in answer_text)
        internal_leakage_records += int("selected_articles/context" in answer_text or "selected_articles" in answer_text)

    if len(ids) != len(set(ids)):
        raise ValueError("duplicate ids found")
    return {
        "records": len(data),
        "unique_ids": len(set(ids)),
        "empty_answer": empty_answer,
        "empty_docs": empty_docs,
        "empty_articles": empty_articles,
        "khong_so_refs_records": khong_so_refs,
        "disclaimer_records": disclaimer_records,
        "internal_leakage_records": internal_leakage_records,
    }


def is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


if __name__ == "__main__":
    raise SystemExit(main())
