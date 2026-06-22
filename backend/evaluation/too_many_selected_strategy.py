"""Design strategy reports for P6.R5 too_many_selected_articles diagnostics.

This module only reads existing reports and writes new analysis artifacts. It
does not modify retrieval, selection, QA, submission, or baseline outputs.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from itertools import combinations
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

EXPECTED_TOTAL_CASES = 216
EXPECTED_CAP = 12
CROSS_LAW = "cross_law_possible_noise"
LEGACY = "legacy_or_version_noise"
TRUNCATION = "answer_truncation_risk"
INSUFFICIENT = "insufficient_basis_risk"

STRATEGY_REPORT = "too_many_selected_strategy_report.md"
STRATEGY_SUMMARY = "too_many_selected_strategy_summary.json"
CANDIDATE_RULES = "candidate_selector_rules.json"
METADATA_ANOMALIES = "law_metadata_anomalies.csv"
SAMPLE_REVIEW = "high_noise_sample_review.csv"

ANOMALY_COLUMNS = ["law_id", "law_title", "anomaly_type", "case_count", "example_ids", "recommended_action"]
SAMPLE_COLUMNS = [
    "id",
    "question",
    "heuristic_category",
    "selected_count",
    "unique_law_count",
    "unique_law_ids",
    "selected_article_ids_preview",
    "answer_preview",
    "observed_pattern",
    "recommended_rule",
    "manual_review_priority",
]
REQUIRED_RULE_FIELDS = [
    "rule_id",
    "name",
    "target_issue",
    "description",
    "proposed_change",
    "expected_benefit",
    "risk",
    "required_validation",
    "priority",
]

KEYWORDS = {
    "doanh_nghiep": ("doanh nghiệp", "kinh doanh", "đăng ký doanh nghiệp"),
    "lao_dong": ("lao động", "người lao động"),
    "thue": ("thuế", "kê khai", "hóa đơn"),
    "so_huu_tri_tue": ("sở hữu trí tuệ", "nhãn hiệu"),
    "bao_hiem": ("bảo hiểm", "bhxh"),
    "ke_toan": ("kế toán", "báo cáo tài chính"),
    "dan_su": ("dân sự", "bộ luật dân sự", "hợp đồng"),
    "xu_phat": ("xử phạt", "mức phạt", "vi phạm"),
}


def build_too_many_selected_strategy(
    p6r5_report_path: str | Path,
    p6r5_summary_path: str | Path,
    law_distribution_path: str | Path,
    samples_md_path: str | Path,
    output_dir: str | Path,
    retrieval_results_path: str | Path | None = None,
    generated_answers_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build P6.R5b strategy files from P6.R5 outputs."""
    rows = read_csv_rows(p6r5_report_path)
    p6r5_summary = read_json(p6r5_summary_path)
    law_rows = read_csv_rows(law_distribution_path)
    samples_md = read_optional_text(samples_md_path)
    retrieval_records = read_jsonl_by_id(retrieval_results_path)
    answer_records = read_jsonl_by_id(generated_answers_path)

    validation = validate_summary_consistency(rows, p6r5_summary)
    cross_law = analyze_cross_law_noise(rows)
    anomalies = detect_metadata_anomalies(rows, law_rows)
    sample_review = build_high_noise_sample_review(rows, answer_records)
    rules = build_candidate_selector_rules()
    decision = recommend_next_task(p6r5_summary, validation)
    summary = {
        "p6r5b_status": "completed",
        "implementation_not_performed": True,
        "report_rows": len(rows),
        "p6r5_validation": validation,
        "p6r5_category_counts": p6r5_summary.get("category_counts", {}),
        "cross_law_analysis": cross_law,
        "metadata_anomaly_count": len(anomalies),
        "metadata_anomaly_counts": dict(Counter(row["anomaly_type"] for row in anomalies)),
        "dominant_issue": decision["dominant_issue"],
        "recommended_next_task": decision["recommended_next_task"],
        "recommended_next_task_reason": decision["recommended_next_task_reason"],
        "candidate_rules_ranked": [rule["rule_id"] for rule in rules],
        "retrieval_record_count": len(retrieval_records),
        "answer_record_count": len(answer_records),
    }

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / STRATEGY_SUMMARY, summary)
    write_json(out / CANDIDATE_RULES, rules)
    write_csv(out / METADATA_ANOMALIES, ANOMALY_COLUMNS, anomalies)
    write_csv(out / SAMPLE_REVIEW, SAMPLE_COLUMNS, sample_review)
    write_strategy_report(out / STRATEGY_REPORT, summary, cross_law, anomalies, sample_review, rules, samples_md)

    return {
        **summary,
        "strategy_report_path": str(out / STRATEGY_REPORT),
        "strategy_summary_path": str(out / STRATEGY_SUMMARY),
        "candidate_rules_path": str(out / CANDIDATE_RULES),
        "metadata_anomalies_path": str(out / METADATA_ANOMALIES),
        "high_noise_sample_review_path": str(out / SAMPLE_REVIEW),
    }


def validate_summary_consistency(report_rows: list[Mapping[str, Any]], summary: Mapping[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    report_count = len(report_rows)
    total = _safe_int(summary.get("total_too_many_selected_cases"))
    category_counts = _safe_dict(summary.get("category_counts"))
    category_sum = sum(_safe_int(value) for value in category_counts.values())
    selected_dist = _safe_dict(summary.get("selected_count_distribution"))

    if total and report_count != total:
        warnings.append(f"report row count {report_count} != summary total {total}")
    if total and category_sum != total:
        warnings.append(f"category count sum {category_sum} != summary total {total}")
    if selected_dist != {str(EXPECTED_CAP): EXPECTED_TOTAL_CASES}:
        warnings.append("selected_count_distribution is not exactly 12:216")

    return {
        "report_rows": report_count,
        "summary_total": total,
        "category_count_sum": category_sum,
        "selected_count_distribution": selected_dist,
        "expected_selected_count_all_cap": selected_dist == {str(EXPECTED_CAP): EXPECTED_TOTAL_CASES},
        "warnings": warnings,
        "is_consistent": not warnings,
    }


def analyze_cross_law_noise(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    selected = [row for row in rows if row.get("heuristic_category") == CROSS_LAW]
    selected_count_dist = Counter(_safe_int(row.get("selected_count")) for row in selected)
    unique_law_dist = Counter(_safe_int(row.get("unique_law_count")) for row in selected)
    keyword_dist = Counter(group_question_keywords(row.get("question")) for row in selected)
    pair_counts: Counter[tuple[str, str]] = Counter()
    for row in selected:
        for pair in combinations(sorted(set(_split_semicolon(row.get("unique_law_ids")))), 2):
            pair_counts[pair] += 1

    total = len(rows)
    return {
        "count": len(selected),
        "percentage": round(len(selected) / total * 100, 2) if total else 0.0,
        "selected_count_distribution": {str(k): v for k, v in sorted(selected_count_dist.items())},
        "unique_law_count_distribution": {str(k): v for k, v in sorted(unique_law_dist.items())},
        "top_law_id_cooccurrences": [
            {"law_id_pair": list(pair), "case_count": count} for pair, count in pair_counts.most_common(20)
        ],
        "top_question_patterns": [{"pattern": key, "case_count": value} for key, value in keyword_dist.most_common(20)],
    }


def detect_metadata_anomalies(
    report_rows: list[Mapping[str, Any]], law_distribution_rows: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    law_examples: dict[str, list[str]] = defaultdict(list)
    law_titles: dict[str, str] = {}
    for row in report_rows:
        law_ids = _split_semicolon(row.get("unique_law_ids"))
        titles = _split_semicolon_preserve_empty(row.get("unique_law_titles_preview"))
        for index, law_id in enumerate(law_ids):
            if len(law_examples[law_id]) < 5:
                law_examples[law_id].append(_safe_text(row.get("id")))
            if law_id not in law_titles and index < len(titles):
                law_titles[law_id] = titles[index]

    for row in law_distribution_rows:
        law_id = _safe_text(row.get("law_id"))
        if not law_id:
            continue
        law_titles.setdefault(law_id, _safe_text(row.get("law_title")))
        if not law_examples[law_id]:
            law_examples[law_id] = _split_semicolon(row.get("example_ids"))[:5]

    anomalies: list[dict[str, Any]] = []
    for law_id, examples in law_examples.items():
        title = law_titles.get(law_id, "")
        for anomaly_type in _law_anomaly_types(law_id, title):
            anomalies.append(
                {
                    "law_id": law_id,
                    "law_title": title,
                    "anomaly_type": anomaly_type,
                    "case_count": _case_count_for_law(law_id, report_rows, law_distribution_rows),
                    "example_ids": ";".join(examples[:5]),
                    "recommended_action": _metadata_recommended_action(anomaly_type),
                }
            )
    anomalies.sort(key=lambda row: (-_safe_int(row["case_count"]), row["anomaly_type"], row["law_id"]))
    return anomalies



def build_high_noise_sample_review(report_rows: list[Mapping[str, Any]], answer_records: Mapping[str, Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    answer_records = answer_records or {}
    picked: dict[str, Mapping[str, Any]] = {}

    def add(rows: list[Mapping[str, Any]], limit: int | None = None) -> None:
        ordered = sorted(rows, key=lambda row: (_safe_int(row.get("unique_law_count")), _safe_int(row.get("selected_count"))), reverse=True)
        for row in ordered[: limit or len(ordered)]:
            picked.setdefault(_safe_text(row.get("id")), row)

    add([row for row in report_rows if row.get("heuristic_category") == CROSS_LAW], 20)
    add([row for row in report_rows if row.get("heuristic_category") == LEGACY], 10)
    add([row for row in report_rows if row.get("heuristic_category") in {TRUNCATION, INSUFFICIENT}])
    rows = [_sample_review_row(row, answer_records.get(_safe_text(row.get("id")), {})) for row in picked.values()]
    rows.sort(key=lambda row: (_priority_rank(row["manual_review_priority"]), -_safe_int(row["unique_law_count"]), row["id"]))
    return rows


def build_candidate_selector_rules() -> list[dict[str, str]]:
    return [
        _rule("candidate_rule_001", "Do not always fill to max selected cap", "selected_count_always_12", "Stop filling selected_articles to the hard cap when score/dropoff evidence is weak.", "Allow selector output below max cap when confidence drops after top candidates.", "Reduces noisy context and prompt pressure.", "May drop useful secondary articles for broad questions.", "Compare selected_count, answer quality, low_confidence categories, and recall on a fixed subset.", "high"),
        _rule("candidate_rule_002", "Cap unique law IDs for non-explicit multi-law questions", "cross_law_possible_noise", "Limit unique law_ids unless the question explicitly asks comparison or multi-law coverage.", "Use query signals to cap unique law_ids around 3-5 for ordinary questions.", "Reduces cross-law noise while keeping article depth.", "Risky for genuine multi-hop questions spanning many laws.", "Track ground-truth article recall and manually review multi-hop samples.", "high"),
        _rule("candidate_rule_003", "Prioritize same-law coherence", "selector_overinclusive", "When top candidates cluster by law_id, prefer coherent same-law articles before unrelated laws.", "Add coherence bonus or diversity penalty across law_ids after initial scoring.", "Improves context focus for specific legal questions.", "May over-focus on a wrong top law if retrieval starts poorly.", "Validate separately on exact-law and cross-law questions.", "high"),
        _rule("candidate_rule_004", "Metadata anomaly quarantine", "legacy_or_version_noise", "Downweight empty law_title, unknown law_id, and law_id/title mismatch candidates unless exact-match evidence is strong.", "Apply metadata quality penalties before final selection.", "Reduces legacy/version noise and malformed citation context.", "Could suppress valid legacy documents for historical questions.", "Inspect legacy samples and exact historical queries.", "medium"),
        _rule("candidate_rule_005", "Legacy version deduplication", "legacy_version_overlap", "Avoid selecting old and new versions of the same legal area unless the query asks historical applicability.", "Group candidate laws by normalized domain/title and keep the most relevant/current cluster.", "Reduces duplicate legal-version context.", "Requires reliable metadata normalization.", "Run metadata audit before enabling broadly.", "medium"),
        _rule("candidate_rule_006", "Answer context budget protection", "answer_truncation_risk", "For high selected_count cases, select fewer stronger articles instead of many short/noisy articles.", "Tie max selected articles to context budget and article text length.", "Reduces truncation and improves answer grounding.", "Could reduce breadth for procedure questions.", "Measure answer_maybe_truncated and answer_insufficient_basis after experiment.", "medium"),
        _rule("candidate_rule_007", "Domain/law family cap", "cross_domain_noise", "Avoid selecting many unrelated laws from different legal domains.", "Use simple domain keywords or law family metadata to cap broad domain spread.", "Targets noisy mixed-domain selections.", "Domain heuristics can be brittle.", "Manually review domain-grouped high-noise samples.", "medium"),
        _rule("candidate_rule_008", "Reranker after candidate retrieval", "subtle_relevance_noise", "If rule-based tightening is insufficient, add Phase 7 reranker before final selection.", "Use a reranker interface to score question-article relevance before selecting articles.", "Better handles subtle relevance than static rules.", "More latency and implementation complexity.", "Compare against rule-based P6.R6 experiment before adopting.", "low"),
    ]


def recommend_next_task(summary: Mapping[str, Any], validation: Mapping[str, Any]) -> dict[str, str]:
    counts = _safe_dict(summary.get("category_counts"))
    total = _safe_int(summary.get("total_too_many_selected_cases"))
    cross = _safe_int(counts.get(CROSS_LAW))
    legacy = _safe_int(counts.get(LEGACY))
    if total and cross / total >= 0.5 and validation.get("expected_selected_count_all_cap"):
        task = "P6.R6_selector_tightening_experiment"
        reason = "cross_law_possible_noise dominates and selected_count is pinned at the max cap"
    elif total and legacy / total >= 0.5:
        task = "P6.R6_metadata_cleanup_analysis"
        reason = "metadata/legacy noise dominates too_many_selected_articles cases"
    elif total and cross / total >= 0.3:
        task = "Phase7_reranker_interface"
        reason = "cross-law relevance appears mixed enough that reranking may be needed"
    else:
        task = "manual_review_required"
        reason = "P6.R5b evidence is inconclusive"
    return {"dominant_issue": _dominant_issue(counts), "recommended_next_task": task, "recommended_next_task_reason": reason}


def write_strategy_report(path: Path, summary: Mapping[str, Any], cross_law: Mapping[str, Any], anomalies: list[Mapping[str, Any]], samples: list[Mapping[str, Any]], rules: list[Mapping[str, Any]], samples_md: str) -> None:
    lines = [
        "# P6.R5b Strategy Report", "", "## Executive summary", "",
        f"- Dominant issue: {summary.get('dominant_issue')}",
        f"- Recommended next task: {summary.get('recommended_next_task')}",
        f"- Reason: {summary.get('recommended_next_task_reason')}",
        "- Implementation performed: no.", "", "## Evidence from P6.R5", "",
        f"- Report rows: {summary.get('report_rows')}",
        f"- Category counts: {json.dumps(summary.get('p6r5_category_counts', {}), ensure_ascii=False, sort_keys=True)}",
        f"- Validation warnings: {json.dumps(summary.get('p6r5_validation', {}).get('warnings', []), ensure_ascii=False)}",
        "", "## Cross-law noise analysis", "",
        f"- Count: {cross_law.get('count')} ({cross_law.get('percentage')}%)",
        f"- selected_count distribution: {json.dumps(cross_law.get('selected_count_distribution', {}), ensure_ascii=False, sort_keys=True)}",
        f"- unique_law_count distribution: {json.dumps(cross_law.get('unique_law_count_distribution', {}), ensure_ascii=False, sort_keys=True)}",
        "- Top question patterns:",
    ]
    for item in cross_law.get("top_question_patterns", [])[:10]:
        lines.append(f"  - {item.get('pattern')}: {item.get('case_count')}")
    lines.extend(["", "## Legacy/version metadata analysis", ""])
    lines.extend([f"- {row.get('law_id')} | {row.get('anomaly_type')} | cases={row.get('case_count')}" for row in anomalies[:20]] or ["- No deterministic metadata anomalies detected."])
    lines.extend(["", "## High-noise examples", ""])
    lines.extend([f"- {row.get('id')} | {row.get('heuristic_category')} | laws={row.get('unique_law_count')} | {row.get('observed_pattern')}" for row in samples[:20]])
    lines.extend(["", "## Candidate selector/retrieval rules", ""])
    lines.extend([f"- {rule['rule_id']} ({rule['priority']}): {rule['name']} - {rule['proposed_change']}" for rule in rules])
    lines.extend(["", "## Recommended next task", "", f"{summary.get('recommended_next_task')}: {summary.get('recommended_next_task_reason')}", "", "## Risks and validation plan", "", "- Track selected_count distribution, low_confidence_count, answer_maybe_truncated, and article recall after any selector experiment.", "- Manually inspect high-noise samples before enabling broad filtering.", "- Keep Phase 7 reranking as a follow-up if rule-based tightening is insufficient."])
    if samples_md:
        lines.append("\n<!-- P6.R5 sample markdown was provided. -->")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")



def group_question_keywords(question: Any) -> str:
    lowered = _safe_text(question).casefold()
    for label, keywords in KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return label
    return "other"


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"CSV input does not exist: {source}")
    with source.open("r", encoding="utf-8", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"JSON input does not exist: {source}")
    loaded = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"JSON input must be an object: {source}")
    return loaded


def read_optional_text(path: str | Path) -> str:
    source = Path(path)
    if not source.is_file():
        logger.warning("Optional samples markdown does not exist: %s", source)
        return ""
    return source.read_text(encoding="utf-8")


def read_jsonl_by_id(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    source = Path(path)
    if not source.is_file():
        logger.warning("Optional JSONL input does not exist: %s", source)
        return {}
    records: dict[str, dict[str, Any]] = {}
    with source.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                loaded = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Skip invalid JSONL line %d in %s: %s", line_number, source, exc)
                continue
            if isinstance(loaded, dict) and _safe_text(loaded.get("id")):
                records[_safe_text(loaded.get("id"))] = loaded
    return records


def write_csv(path: Path, columns: list[str], rows: list[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _law_anomaly_types(law_id: str, law_title: str) -> list[str]:
    anomalies: list[str] = []
    if not _safe_text(law_title):
        anomalies.append("empty_law_title")
    if _safe_text(law_id).casefold() in {"kh?ng s?", "khong so", "unknown", "none", "null", ""}:
        anomalies.append("unknown_law_id")
    if _title_mismatch_suspected(law_id, law_title):
        anomalies.append("law_id_title_mismatch_suspected")
    if _legacy_version_suspected(law_id, law_title):
        anomalies.append("legacy_version_overlap")
    return anomalies


def _title_mismatch_suspected(law_id: str, law_title: str) -> bool:
    law_id = _safe_text(law_id).upper()
    title = _safe_text(law_title).upper()
    if not law_id or not title:
        return False
    title_numbers = set(re.findall(r"\b\d{1,4}/\d{4}/[A-Z?0-9-]+\b", title))
    return bool(title_numbers and law_id not in title_numbers)


def _legacy_version_suspected(law_id: str, law_title: str) -> bool:
    return bool(re.search(r"\b(19[0-9]{2}|2000|2001|2002|2003|2004|2005)\b", f"{law_id} {law_title}"))


def _metadata_recommended_action(anomaly_type: str) -> str:
    return {
        "empty_law_title": "Backfill law_title from canonical registry before selector tuning.",
        "unknown_law_id": "Normalize or quarantine unknown law_id candidates unless exact-match evidence is strong.",
        "law_id_title_mismatch_suspected": "Audit law_id/title mapping and fix canonical metadata.",
        "legacy_version_overlap": "Deduplicate legacy/current versions unless the query asks historical applicability.",
    }.get(anomaly_type, "Manual metadata review.")


def _sample_review_row(row: Mapping[str, Any], answer_record: Mapping[str, Any]) -> dict[str, Any]:
    category = _safe_text(row.get("heuristic_category"))
    unique_law_count = _safe_int(row.get("unique_law_count"))
    return {
        "id": _safe_text(row.get("id")),
        "question": _safe_text(row.get("question")),
        "heuristic_category": category,
        "selected_count": _safe_int(row.get("selected_count")),
        "unique_law_count": unique_law_count,
        "unique_law_ids": _safe_text(row.get("unique_law_ids")),
        "selected_article_ids_preview": _safe_text(row.get("selected_article_ids_preview")),
        "answer_preview": _safe_text(answer_record.get("answer"))[:300] or _safe_text(row.get("answer_preview")),
        "observed_pattern": _observed_pattern(category),
        "recommended_rule": _recommended_rule_for_category(category),
        "manual_review_priority": _manual_review_priority(category, unique_law_count),
    }


def _observed_pattern(category: str) -> str:
    return {
        CROSS_LAW: "selected articles span many law_ids; likely cap-filling cross-law noise",
        LEGACY: "selected articles include legacy or metadata-anomalous law_ids",
        TRUNCATION: "too many selected articles overlap answer truncation risk",
        INSUFFICIENT: "many selected articles still leave insufficient basis",
    }.get(category, "manual review needed")


def _recommended_rule_for_category(category: str) -> str:
    return {
        CROSS_LAW: "candidate_rule_001,candidate_rule_002,candidate_rule_003",
        LEGACY: "candidate_rule_004,candidate_rule_005",
        TRUNCATION: "candidate_rule_006",
        INSUFFICIENT: "candidate_rule_001,candidate_rule_008",
    }.get(category, "candidate_rule_008")


def _manual_review_priority(category: str, unique_law_count: int) -> str:
    if category in {TRUNCATION, INSUFFICIENT} or unique_law_count >= 10:
        return "high"
    if category in {CROSS_LAW, LEGACY}:
        return "medium"
    return "low"


def _priority_rank(priority: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(priority, 3)


def _rule(rule_id: str, name: str, target_issue: str, description: str, proposed_change: str, expected_benefit: str, risk: str, required_validation: str, priority: str) -> dict[str, str]:
    return {"rule_id": rule_id, "name": name, "target_issue": target_issue, "description": description, "proposed_change": proposed_change, "expected_benefit": expected_benefit, "risk": risk, "required_validation": required_validation, "priority": priority}


def _case_count_for_law(law_id: str, report_rows: list[Mapping[str, Any]], law_rows: list[Mapping[str, Any]]) -> int:
    for row in law_rows:
        if _safe_text(row.get("law_id")) == law_id:
            return _safe_int(row.get("case_count"))
    return sum(1 for row in report_rows if law_id in _split_semicolon(row.get("unique_law_ids")))


def _dominant_issue(counts: Mapping[str, Any]) -> str:
    if not counts:
        return "unknown"
    return max(counts.items(), key=lambda item: _safe_int(item[1]))[0]


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _split_semicolon(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


def _split_semicolon_preserve_empty(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split(";")]


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float):
        return max(int(value), 0)
    if isinstance(value, str):
        try:
            return max(int(float(value.strip())), 0)
        except ValueError:
            return 0
    return 0


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
