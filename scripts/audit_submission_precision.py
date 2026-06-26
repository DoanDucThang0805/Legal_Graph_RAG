"""Audit precision risk signals in a submission JSON file."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from scripts.prune_submission_citations import CONFLICT_GROUPS, LOCAL_DOC_PATTERNS, parse_article_ref


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit submission citation precision risk signals.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    records = json.loads(Path(args.input).read_text(encoding="utf-8"))
    rows = [audit_record(record) for record in records]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_summary(output_dir / "audit_precision_summary.json", rows, args.input)
    write_csv(output_dir / "audit_precision_by_record.csv", rows)
    risky = sorted(rows, key=lambda row: risk_score(row), reverse=True)[:100]
    write_csv(output_dir / "top_risky_precision_records.csv", risky)
    return 0


def audit_record(record: dict[str, Any]) -> dict[str, Any]:
    docs = list(record.get("relevant_docs") or [])
    articles = list(record.get("relevant_articles") or [])
    answer = str(record.get("answer") or "")
    article_refs = [ref for ref in (parse_article_ref(article) for article in articles) if ref is not None]
    article_nos = [ref.article_no for ref in article_refs]
    mentioned = sum(1 for article_no in article_nos if article_no.casefold() in answer.casefold())
    conflicts = conflict_flags({ref.law_id for ref in article_refs})
    return {
        "id": record.get("id"),
        "docs_count": len(docs),
        "articles_count": len(articles),
        "docs_gt_3": len(docs) > 3,
        "articles_gt_4": len(articles) > 4,
        "docs_gt_5": len(docs) > 5,
        "articles_gt_5": len(articles) > 5,
        "local_docs_count": sum(1 for doc in docs if is_local_doc_text(doc)),
        "answer_legal_basis_lines_count": count_legal_basis_lines(answer),
        "articles_mentioned_in_answer_count": mentioned,
        "articles_not_mentioned_in_answer_count": max(0, len(articles) - mentioned),
        **conflicts,
    }


def conflict_flags(law_ids: set[str]) -> dict[str, bool]:
    names = (
        "tax_law_2006_2019",
        "bidding_law_2013_2023",
        "sme_decree_2018_2021",
        "labor_penalty_2013_2022",
    )
    return {
        name: old_law in law_ids and new_law in law_ids
        for name, (old_law, new_law) in zip(names, CONFLICT_GROUPS, strict=True)
    }


def count_legal_basis_lines(answer: str) -> int:
    return sum(1 for line in answer.splitlines() if "Điều" in line or "điều" in line)


def is_local_doc_text(text: str) -> bool:
    folded = str(text).casefold()
    return any(pattern.casefold() in folded for pattern in LOCAL_DOC_PATTERNS)


def write_summary(path: Path, rows: list[dict[str, Any]], input_path: str) -> None:
    docs_dist = Counter(row["docs_count"] for row in rows)
    articles_dist = Counter(row["articles_count"] for row in rows)
    summary = {
        "input_path": input_path,
        "total_records": len(rows),
        "docs_count_distribution": dict(sorted(docs_dist.items())),
        "articles_count_distribution": dict(sorted(articles_dist.items())),
        "docs_gt_3_count": sum(row["docs_gt_3"] for row in rows),
        "articles_gt_4_count": sum(row["articles_gt_4"] for row in rows),
        "docs_gt_5_count": sum(row["docs_gt_5"] for row in rows),
        "articles_gt_5_count": sum(row["articles_gt_5"] for row in rows),
        "local_docs_records": sum(row["local_docs_count"] > 0 for row in rows),
        "top_risky_record_ids": [row["id"] for row in sorted(rows, key=lambda row: risk_score(row), reverse=True)[:20]],
    }
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def risk_score(row: dict[str, Any]) -> int:
    return (
        int(row["docs_count"]) * 2
        + int(row["articles_count"]) * 3
        + int(row["local_docs_count"]) * 4
        + int(row["articles_not_mentioned_in_answer_count"]) * 5
        + sum(int(row[key]) * 10 for key in row if key.endswith("_2019") or key.endswith("_2023") or key.endswith("_2021") or key.endswith("_2022"))
    )


if __name__ == "__main__":
    raise SystemExit(main())
