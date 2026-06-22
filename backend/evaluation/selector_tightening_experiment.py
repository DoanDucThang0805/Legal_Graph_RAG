"""Experiment-only selector tightening for existing retrieval results.

This module rewrites selected_articles in a copied retrieval_results JSONL for
diagnostic evaluation. It does not rerun retrieval, call LLMs, or change the
production selector.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TIGHTENED_JSONL = "retrieval_results_p6r6_tightened.jsonl"
REPORT_CSV = "selector_tightening_report.csv"
SUMMARY_JSON = "selector_tightening_summary.json"
SAMPLES_MD = "selector_tightening_samples.md"
CONFIG_JSON = "selector_tightening_config.json"

UNKNOWN_LAW_IDS = {"", "none", "null", "unknown", "khong so", "không số", "khong ro", "không rõ"}
EXPLICIT_MULTILAW_SIGNALS = (
    "so sánh",
    "khác nhau",
    "điểm khác biệt",
    "đồng thời theo",
    "theo các luật",
    "theo những văn bản nào",
    "các văn bản",
    "nhiều văn bản",
    "quy định nào liên quan đến",
    "liệt kê các quy định",
)

REPORT_COLUMNS = [
    "id",
    "question",
    "is_too_many_selected_case",
    "original_selected_count",
    "tightened_selected_count",
    "selected_count_delta",
    "original_unique_law_count",
    "tightened_unique_law_count",
    "unique_law_count_delta",
    "explicit_multilaw_question",
    "rules_applied",
    "removed_article_ids_preview",
    "kept_article_ids_preview",
    "risk_flag",
    "risk_reason",
]


@dataclass(frozen=True)
class SelectorTighteningConfig:
    max_selected: int = 8
    max_unique_law_ids: int = 5
    min_keep: int = 3
    preserve_explicit_multilaw: bool = True
    metadata_penalty: bool = True
    same_law_coherence: bool = True
    include_debug_field: bool = True


@dataclass(frozen=True)
class ArticleRef:
    article_id: str
    law_id: str
    law_title: str
    article_no: str


def parse_article_id(article_id: str) -> ArticleRef:
    text = _safe_text(article_id)
    parts = [part.strip() for part in text.split("|")]
    if len(parts) >= 3:
        return ArticleRef(article_id=text, law_id=parts[0], law_title=parts[1], article_no=parts[2])
    return ArticleRef(article_id=text, law_id="", law_title="", article_no="")


def extract_selected_articles(row: Mapping[str, Any]) -> list[str]:
    selected = _safe_list(row.get("selected_articles"))
    result: list[str] = []
    for item in selected:
        if isinstance(item, str):
            article_id = item.strip()
        elif isinstance(item, Mapping):
            article_id = _safe_text(item.get("article_id"))
        else:
            article_id = ""
        if article_id:
            result.append(article_id)
    return result


def set_selected_articles(row: Mapping[str, Any], tightened_article_ids: list[str]) -> dict[str, Any]:
    output = dict(row)
    output["selected_articles"] = list(tightened_article_ids)
    return output


def is_explicit_multilaw_question(question: str) -> bool:
    lowered = _safe_text(question).casefold()
    return any(signal in lowered for signal in EXPLICIT_MULTILAW_SIGNALS)


def metadata_quality_penalty(ref: ArticleRef) -> float:
    penalty = 0.0
    law_id = ref.law_id
    law_title = ref.law_title
    article_id = ref.article_id
    if law_id.casefold() in UNKNOWN_LAW_IDS:
        penalty += 2.0
    if not law_title:
        penalty += 1.0
    if _law_id_title_mismatch(law_id, law_title):
        penalty += 1.5
    if article_id and len([part for part in article_id.split("|") if part.strip()]) < 3:
        penalty += 1.0
    if not article_id:
        penalty += 0.5
    return penalty


def compute_law_cluster_strength(selected_articles: list[ArticleRef]) -> dict[str, Any]:
    law_counts = Counter(_law_id(ref) for ref in selected_articles if _law_id(ref))
    primary_law_id = ""
    if law_counts:
        primary_law_id = law_counts.most_common(1)[0][0]
    return {"primary_law_id": primary_law_id, "law_counts": dict(law_counts)}


def tighten_selected_articles(
    question: str,
    selected_article_ids: list[str],
    config: SelectorTighteningConfig,
) -> tuple[list[str], dict[str, Any]]:
    original_ids = [article_id for article_id in selected_article_ids if _safe_text(article_id)]
    refs = [parse_article_id(article_id) for article_id in original_ids]
    original_count = len(refs)
    if original_count <= config.min_keep:
        debug = _build_debug(question, refs, refs, [], config, [])
        return original_ids, debug

    explicit_multilaw = is_explicit_multilaw_question(question)
    cluster = compute_law_cluster_strength(refs)
    primary_law_id = _safe_text(cluster.get("primary_law_id"))
    rules_applied: list[str] = []

    scored: list[tuple[float, int, ArticleRef]] = []
    for index, ref in enumerate(refs):
        score = _base_rank_score(ref, index)
        if config.metadata_penalty:
            score -= metadata_quality_penalty(ref)
        if config.same_law_coherence and primary_law_id and _law_id(ref) == primary_law_id:
            score += 0.75
        scored.append((score, index, ref))

    if config.metadata_penalty:
        rules_applied.append("metadata_penalty")
    if config.same_law_coherence:
        rules_applied.append("same_law_coherence")

    ranked = sorted(scored, key=lambda item: (-item[0], item[1]))
    law_cap = None if explicit_multilaw and config.preserve_explicit_multilaw else max(config.max_unique_law_ids, 1)
    if law_cap is not None:
        rules_applied.append("max_unique_law_ids")
    if config.max_selected < original_count:
        rules_applied.append("max_selected")

    kept: list[ArticleRef] = []
    kept_laws: set[str] = set()
    target_count = min(max(config.min_keep, config.max_selected), original_count)
    for _, _, ref in ranked:
        law_id = _law_id(ref)
        if law_cap is not None and law_id and law_id not in kept_laws and len(kept_laws) >= law_cap:
            continue
        kept.append(ref)
        if law_id:
            kept_laws.add(law_id)
        if len(kept) >= target_count:
            break

    if len(kept) < min(config.min_keep, original_count):
        kept_ids = {ref.article_id for ref in kept}
        for _, _, ref in ranked:
            if ref.article_id in kept_ids:
                continue
            kept.append(ref)
            kept_ids.add(ref.article_id)
            if len(kept) >= min(config.min_keep, original_count):
                break

    kept_ids = {ref.article_id for ref in kept}
    kept_in_original_order = [ref for ref in refs if ref.article_id in kept_ids]
    removed = [ref for ref in refs if ref.article_id not in kept_ids]
    debug = _build_debug(question, refs, kept_in_original_order, removed, config, rules_applied)
    return [ref.article_id for ref in kept_in_original_order], debug


def run_selector_tightening_experiment(
    retrieval_results_path: str | Path,
    low_confidence_path: str | Path,
    p6r5_report_path: str | Path,
    p6r5b_summary_path: str | Path,
    candidate_rules_path: str | Path,
    output_dir: str | Path,
    config: SelectorTighteningConfig | None = None,
) -> dict[str, Any]:
    config = config or SelectorTighteningConfig()
    records = read_jsonl_records(retrieval_results_path)
    too_many_ids = read_too_many_ids(low_confidence_path, p6r5_report_path)
    # These files are loaded to validate availability and preserve experiment provenance.
    p6r5b_summary = read_optional_json(p6r5b_summary_path)
    candidate_rules = read_optional_json(candidate_rules_path)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    tightened_path = output_path / TIGHTENED_JSONL
    report_rows: list[dict[str, Any]] = []
    tightened_records: list[dict[str, Any]] = []

    rows_with_selected = 0
    rows_without_selected = 0
    selected_item_type = ""
    for record in records:
        selected_article_ids = extract_selected_articles(record)
        if selected_article_ids:
            rows_with_selected += 1
            if not selected_item_type:
                selected_item_type = _selected_item_type(record)
        else:
            rows_without_selected += 1
        tightened, debug = tighten_selected_articles(_safe_text(record.get("question")), selected_article_ids, config)
        output_record = set_selected_articles(record, tightened)
        if config.include_debug_field:
            output_record["p6r6_selector_tightening_debug"] = debug
        tightened_records.append(output_record)
        report_rows.append(_build_report_row(record, debug, _safe_text(record.get("id")) in too_many_ids))

    if rows_with_selected == 0:
        raise ValueError('No selected articles found in retrieval_results. Expected row["selected_articles"] as list[str] or list[dict].')

    write_jsonl(tightened_path, tightened_records)
    write_csv(output_path / REPORT_CSV, REPORT_COLUMNS, report_rows)
    summary = build_summary(report_rows, config, records, too_many_ids, p6r5b_summary, candidate_rules, rows_with_selected=rows_with_selected, rows_without_selected=rows_without_selected, selected_item_type=selected_item_type)
    write_json(output_path / SUMMARY_JSON, summary)
    write_json(output_path / CONFIG_JSON, asdict(config))
    write_samples_markdown(output_path / SAMPLES_MD, report_rows)
    return {
        **summary,
        "tightened_retrieval_results_path": str(tightened_path),
        "report_path": str(output_path / REPORT_CSV),
        "summary_path": str(output_path / SUMMARY_JSON),
        "samples_path": str(output_path / SAMPLES_MD),
        "config_path": str(output_path / CONFIG_JSON),
    }


def build_summary(
    report_rows: list[Mapping[str, Any]],
    config: SelectorTighteningConfig,
    retrieval_records: Sequence[Mapping[str, Any]],
    too_many_ids: set[str],
    p6r5b_summary: Mapping[str, Any] | None = None,
    candidate_rules: Any | None = None,
    rows_with_selected: int = 0,
    rows_without_selected: int = 0,
    selected_item_type: str = "",
) -> dict[str, Any]:
    baseline_selected = Counter(_safe_int(row.get("original_selected_count")) for row in report_rows)
    tightened_selected = Counter(_safe_int(row.get("tightened_selected_count")) for row in report_rows)
    baseline_law = Counter(_safe_int(row.get("original_unique_law_count")) for row in report_rows)
    tightened_law = Counter(_safe_int(row.get("tightened_unique_law_count")) for row in report_rows)
    reduced_selected = sum(_safe_int(row.get("selected_count_delta")) > 0 for row in report_rows)
    reduced_law = sum(_safe_int(row.get("unique_law_count_delta")) > 0 for row in report_rows)
    recall_loss = sum(row.get("risk_flag") in {"possible_recall_loss", "too_aggressive", "explicit_multilaw_pruned"} for row in report_rows)
    explicit_multilaw = sum(_as_bool(row.get("explicit_multilaw_question")) for row in report_rows)
    too_many_after = sum(
        row.get("is_too_many_selected_case") is True and _safe_int(row.get("tightened_selected_count")) >= 12
        for row in report_rows
    )
    p6r5_checked = sum(1 for row in report_rows if _safe_text(row.get("id")) in too_many_ids)
    p6r5_count_12 = sum(1 for row in report_rows if _safe_text(row.get("id")) in too_many_ids and _safe_int(row.get("original_selected_count")) == 12)
    warnings: list[str] = []
    if len(too_many_ids) and p6r5_count_12 != len(too_many_ids):
        warnings.append(f"P6.R5 too_many cases with original_selected_count=12 is {p6r5_count_12}, expected {len(too_many_ids)}")
    recommended_next_step, reason = _recommend_next_step(too_many_after, len(too_many_ids), recall_loss)
    return {
        "p6r6_status": "completed",
        "implementation_mode": "experiment_only",
        "retrieval_rows": len(retrieval_records),
        "too_many_selected_cases_input": len(too_many_ids),
        "selected_articles_source_path": "selected_articles",
        "selected_article_item_type": selected_item_type,
        "rows_with_selected_articles": rows_with_selected,
        "rows_without_selected_articles": rows_without_selected,
        "config": asdict(config),
        "baseline_selected_count_distribution": _counter_to_dict(baseline_selected),
        "tightened_selected_count_distribution": _counter_to_dict(tightened_selected),
        "baseline_unique_law_count_distribution": _counter_to_dict(baseline_law),
        "tightened_unique_law_count_distribution": _counter_to_dict(tightened_law),
        "too_many_selected_cases_after_tightening": too_many_after,
        "cases_reduced_selected_count": reduced_selected,
        "cases_reduced_unique_law_count": reduced_law,
        "possible_recall_loss_cases": recall_loss,
        "explicit_multilaw_cases": explicit_multilaw,
        "p6r5_too_many_cases_checked": p6r5_checked,
        "p6r5_too_many_cases_with_original_count_12": p6r5_count_12,
        "warnings": warnings,
        "recommended_next_step": recommended_next_step,
        "recommended_next_step_reason": reason,
        "p6r5b_recommended_next_task": (p6r5b_summary or {}).get("recommended_next_task", ""),
        "candidate_rule_count": len(candidate_rules) if isinstance(candidate_rules, list) else 0,
    }


def read_too_many_ids(low_confidence_path: str | Path, p6r5_report_path: str | Path) -> set[str]:
    ids: set[str] = set()
    for row in read_csv_rows(low_confidence_path):
        issues = str(row.get("issue_categories") or "").replace("|", ";").replace(",", ";").split(";")
        if "too_many_selected_articles" in {issue.strip() for issue in issues}:
            ids.add(_safe_text(row.get("id")))
    if ids:
        return ids
    return {_safe_text(row.get("id")) for row in read_csv_rows(p6r5_report_path) if _safe_text(row.get("id"))}




def read_jsonl_records(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"retrieval results JSONL does not exist: {source}")
    records: list[dict[str, Any]] = []
    with source.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            loaded = json.loads(line)
            if not isinstance(loaded, dict):
                raise ValueError(f"JSONL line {line_number} must be an object")
            records.append(loaded)
    return records


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    if not source.is_file():
        logger.warning("CSV input does not exist: %s", source)
        return []
    with source.open("r", encoding="utf-8", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def read_optional_json(path: str | Path) -> Any:
    source = Path(path)
    if not source.is_file():
        logger.warning("Optional JSON input does not exist: %s", source)
        return None
    return json.loads(source.read_text(encoding="utf-8"))


def write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_csv(path: Path, columns: list[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_samples_markdown(path: Path, rows: list[Mapping[str, Any]]) -> None:
    high_impact = sorted(rows, key=lambda row: _safe_int(row.get("selected_count_delta")), reverse=True)[:10]
    recall_loss = [row for row in rows if row.get("risk_flag") != "none"][:10]
    explicit = [row for row in rows if _as_bool(row.get("explicit_multilaw_question"))][:10]
    metadata = [row for row in rows if row.get("risk_flag") == "metadata_only_pruning"][:10]
    lines = ["# P6.R6 Selector Tightening Samples", "", "## Summary", "", f"- Rows: {len(rows)}", ""]
    _append_sample_section(lines, "High-impact reduced cases", high_impact)
    _append_sample_section(lines, "Possible recall loss cases", recall_loss)
    _append_sample_section(lines, "Explicit multi-law preserved cases", explicit)
    _append_sample_section(lines, "Metadata anomaly pruning examples", metadata)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_sample_section(lines: list[str], title: str, rows: Sequence[Mapping[str, Any]]) -> None:
    lines.extend([f"## {title}", ""])
    if not rows:
        lines.extend(["- none", ""])
        return
    for row in rows:
        lines.extend([f"- id: {row.get('id')}", f"  question: {_safe_text(row.get('question'))[:240]}", f"  selected: {row.get('original_selected_count')} -> {row.get('tightened_selected_count')}", f"  unique_law: {row.get('original_unique_law_count')} -> {row.get('tightened_unique_law_count')}", f"  removed: {row.get('removed_article_ids_preview')}", f"  risk: {row.get('risk_flag')} ({row.get('risk_reason')})", ""])


def _build_report_row(record: Mapping[str, Any], debug: Mapping[str, Any], is_too_many: bool) -> dict[str, Any]:
    original_count = _safe_int(debug.get("original_selected_count"))
    tightened_count = _safe_int(debug.get("tightened_selected_count"))
    original_laws = _safe_int(debug.get("original_unique_law_count"))
    tightened_laws = _safe_int(debug.get("tightened_unique_law_count"))
    risk_flag, risk_reason = _risk_flag(debug)
    return {"id": _safe_text(record.get("id")), "question": _safe_text(record.get("question")), "is_too_many_selected_case": is_too_many, "original_selected_count": original_count, "tightened_selected_count": tightened_count, "selected_count_delta": original_count - tightened_count, "original_unique_law_count": original_laws, "tightened_unique_law_count": tightened_laws, "unique_law_count_delta": original_laws - tightened_laws, "explicit_multilaw_question": bool(debug.get("explicit_multilaw_question")), "rules_applied": ";".join(_safe_list(debug.get("rules_applied"))), "removed_article_ids_preview": ";".join(_safe_list(debug.get("removed_article_ids_preview"))), "kept_article_ids_preview": ";".join(_safe_list(debug.get("kept_article_ids_preview"))), "risk_flag": risk_flag, "risk_reason": risk_reason}


def _risk_flag(debug: Mapping[str, Any]) -> tuple[str, str]:
    original_count = _safe_int(debug.get("original_selected_count"))
    tightened_count = _safe_int(debug.get("tightened_selected_count"))
    original_laws = _safe_int(debug.get("original_unique_law_count"))
    tightened_laws = _safe_int(debug.get("tightened_unique_law_count"))
    removed_count = original_count - tightened_count
    if tightened_count < 3 and original_count >= 8:
        return "too_aggressive", "tightened selected_count below 3 for a broad original selection"
    if bool(debug.get("explicit_multilaw_question")) and original_laws - tightened_laws >= 3:
        return "explicit_multilaw_pruned", "explicit multi-law question lost several law_ids"
    if original_count >= 8 and removed_count >= max(6, original_count // 2):
        return "possible_recall_loss", "large fraction of selected articles removed"
    rules = set(_safe_list(debug.get("rules_applied")))
    if removed_count > 0 and rules == {"metadata_penalty"}:
        return "metadata_only_pruning", "only metadata penalty affected pruning"
    return "none", ""


def _build_debug(question: str, original: list[ArticleRef], tightened: list[ArticleRef], removed: list[ArticleRef], config: SelectorTighteningConfig, rules_applied: list[str]) -> dict[str, Any]:
    original_laws = _unique_law_ids(original)
    tightened_laws = _unique_law_ids(tightened)
    return {"selected_articles_source_path": "selected_articles", "selected_article_item_type": "str", "original_selected_count": len(original), "tightened_selected_count": len(tightened), "original_unique_law_count": len(original_laws), "tightened_unique_law_count": len(tightened_laws), "explicit_multilaw_question": is_explicit_multilaw_question(question), "rules_applied": rules_applied, "removed_article_ids_preview": [_article_id(article) for article in removed[:8]], "kept_article_ids_preview": [_article_id(article) for article in tightened[:8]], "config": asdict(config)}


def _recommend_next_step(too_many_after: int, too_many_before: int, recall_loss: int) -> tuple[str, str]:
    if too_many_before and too_many_after <= too_many_before * 0.25 and recall_loss <= max(5, too_many_before * 0.1):
        return "P6.R6b_regenerate_answers_on_tightened_subset", "tightening substantially reduces too_many_selected with low estimated recall risk"
    if recall_loss > max(10, too_many_before * 0.2):
        return "P6.R6a_tune_selector_tightening_config", "possible recall loss cases are high"
    if too_many_before and too_many_after >= too_many_before * 0.75:
        return "Phase7_reranker_interface", "rule-based tightening has little effect"
    return "P6.R6a_tune_selector_tightening_config", "review samples and tune experiment config before answer regeneration"



def _base_rank_score(ref: ArticleRef, index: int) -> float:
    return 1000.0 - index


def _law_id_title_mismatch(law_id: str, law_title: str) -> bool:
    if not law_id or not law_title:
        return False
    title_ids = set(re.findall(r"\b\d{1,4}/\d{4}/[A-Z?0-9-]+\b", law_title.upper()))
    return bool(title_ids and law_id.upper() not in title_ids)


def _unique_law_ids(articles: Sequence[ArticleRef]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for article in articles:
        law_id = _law_id(article)
        if law_id and law_id not in seen:
            seen.add(law_id)
            result.append(law_id)
    return result


def _law_id(ref: ArticleRef) -> str:
    return _safe_text(ref.law_id) or "__UNKNOWN__"


def _article_id(ref: ArticleRef) -> str:
    return ref.article_id


def _selected_item_type(row: Mapping[str, Any]) -> str:
    selected = _safe_list(row.get("selected_articles"))
    if not selected:
        return ""
    first = selected[0]
    if isinstance(first, str):
        return "str"
    if isinstance(first, Mapping):
        return "dict"
    return type(first).__name__


def _counter_to_dict(counter: Counter[int]) -> dict[str, int]:
    return {str(key): value for key, value in sorted(counter.items())}


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"true", "1", "yes"}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


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


GRID_COMPARISON_CSV = "selector_tuning_comparison.csv"
GRID_SUMMARY_JSON = "selector_tuning_summary.json"
GRID_RECOMMENDATION_MD = "selector_tuning_recommendation.md"

GRID_COMPARISON_COLUMNS = [
    "config_name",
    "max_selected",
    "max_unique_law_ids",
    "min_keep",
    "metadata_penalty",
    "same_law_coherence",
    "too_many_selected_cases_after_tightening",
    "cases_reduced_selected_count",
    "cases_reduced_unique_law_count",
    "possible_recall_loss_cases",
    "explicit_multilaw_cases",
    "avg_selected_count_before",
    "avg_selected_count_after",
    "avg_unique_law_count_before",
    "avg_unique_law_count_after",
    "selected_count_distribution_after",
    "unique_law_count_distribution_after",
    "p6r5_too_many_cases_with_original_count_12",
]


def default_tuning_configs() -> dict[str, SelectorTighteningConfig]:
    return {
        "baseline_strict": SelectorTighteningConfig(max_selected=8, max_unique_law_ids=5, min_keep=3, metadata_penalty=True, same_law_coherence=True),
        "balanced_9_6": SelectorTighteningConfig(max_selected=9, max_unique_law_ids=6, min_keep=4, metadata_penalty=True, same_law_coherence=True),
        "balanced_10_6": SelectorTighteningConfig(max_selected=10, max_unique_law_ids=6, min_keep=4, metadata_penalty=True, same_law_coherence=True),
        "soft_10_7": SelectorTighteningConfig(max_selected=10, max_unique_law_ids=7, min_keep=4, metadata_penalty=True, same_law_coherence=True),
        "count_only_10": SelectorTighteningConfig(max_selected=10, max_unique_law_ids=99, min_keep=4, metadata_penalty=False, same_law_coherence=False),
        "law_cap_only_7": SelectorTighteningConfig(max_selected=12, max_unique_law_ids=7, min_keep=4, metadata_penalty=True, same_law_coherence=True),
    }


def run_selector_tightening_grid(
    retrieval_results_path: str | Path,
    low_confidence_path: str | Path,
    p6r5_report_path: str | Path,
    p6r5b_summary_path: str | Path,
    candidate_rules_path: str | Path,
    output_dir: str | Path,
    configs: Mapping[str, SelectorTighteningConfig] | None = None,
) -> dict[str, Any]:
    configs = dict(configs or default_tuning_configs())
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    comparison_rows: list[dict[str, Any]] = []
    summaries: dict[str, dict[str, Any]] = {}

    for config_name, config in configs.items():
        config_output_dir = output_path / f"config_{config_name}"
        summary = run_selector_tightening_experiment(
            retrieval_results_path=retrieval_results_path,
            low_confidence_path=low_confidence_path,
            p6r5_report_path=p6r5_report_path,
            p6r5b_summary_path=p6r5b_summary_path,
            candidate_rules_path=candidate_rules_path,
            output_dir=config_output_dir,
            config=config,
        )
        summaries[config_name] = summary
        comparison_rows.append(_comparison_row(config_name, summary))

    recommendation = recommend_tuning_config(comparison_rows)
    grid_summary = {
        "p6r6b_status": "completed",
        "implementation_mode": "grid_experiment_only",
        "config_count": len(configs),
        "recommended_config": recommendation["recommended_config"],
        "recommended_next_step": recommendation["recommended_next_step"],
        "recommended_reason": recommendation["recommended_reason"],
        "comparison_rows": comparison_rows,
    }
    write_csv(output_path / GRID_COMPARISON_CSV, GRID_COMPARISON_COLUMNS, comparison_rows)
    write_json(output_path / GRID_SUMMARY_JSON, grid_summary)
    write_tuning_recommendation_markdown(output_path / GRID_RECOMMENDATION_MD, grid_summary)
    return {
        **grid_summary,
        "comparison_path": str(output_path / GRID_COMPARISON_CSV),
        "summary_path": str(output_path / GRID_SUMMARY_JSON),
        "recommendation_path": str(output_path / GRID_RECOMMENDATION_MD),
    }


def recommend_tuning_config(comparison_rows: list[Mapping[str, Any]]) -> dict[str, str]:
    eligible: list[Mapping[str, Any]] = []
    for row in comparison_rows:
        too_many_after = _safe_int(row.get("too_many_selected_cases_after_tightening"))
        recall_loss = _safe_int(row.get("possible_recall_loss_cases"))
        if too_many_after <= 108 and recall_loss <= 25:
            eligible.append(row)
    if eligible:
        best = sorted(eligible, key=lambda row: (_safe_int(row.get("possible_recall_loss_cases")), _safe_int(row.get("too_many_selected_cases_after_tightening")), -_safe_int(row.get("avg_selected_count_after"))))[0]
        return {
            "recommended_config": _safe_text(best.get("config_name")),
            "recommended_next_step": "P6.R6b_regenerate_answers_on_tightened_subset",
            "recommended_reason": "config reduces too_many_selected by at least 50% with possible_recall_loss_cases <= 25",
        }
    if not comparison_rows:
        return {"recommended_config": "", "recommended_next_step": "manual_review_required", "recommended_reason": "no configs were evaluated"}
    lowest_risk = sorted(comparison_rows, key=lambda row: _safe_int(row.get("possible_recall_loss_cases")))[0]
    if _safe_int(lowest_risk.get("too_many_selected_cases_after_tightening")) >= 162:
        return {
            "recommended_config": _safe_text(lowest_risk.get("config_name")),
            "recommended_next_step": "Phase7_reranker_interface",
            "recommended_reason": "rule-based configs have little effect at acceptable recall risk",
        }
    return {
        "recommended_config": _safe_text(lowest_risk.get("config_name")),
        "recommended_next_step": "P6.R6a_tune_selector_tightening_config",
        "recommended_reason": "no config satisfies both reduction and recall-risk thresholds",
    }


def write_tuning_recommendation_markdown(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# P6.R6b Selector Tightening Tuning Recommendation",
        "",
        f"- Recommended config: {summary.get('recommended_config')}",
        f"- Recommended next step: {summary.get('recommended_next_step')}",
        f"- Reason: {summary.get('recommended_reason')}",
        "",
        "## Comparison",
        "",
    ]
    for row in summary.get("comparison_rows", []):
        lines.append(
            f"- {row.get('config_name')}: too_many_after={row.get('too_many_selected_cases_after_tightening')}, "
            f"recall_loss={row.get('possible_recall_loss_cases')}, avg_selected_after={row.get('avg_selected_count_after')}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _comparison_row(config_name: str, summary: Mapping[str, Any]) -> dict[str, Any]:
    config = summary.get("config", {}) if isinstance(summary.get("config"), Mapping) else {}
    return {
        "config_name": config_name,
        "max_selected": config.get("max_selected", ""),
        "max_unique_law_ids": config.get("max_unique_law_ids", ""),
        "min_keep": config.get("min_keep", ""),
        "metadata_penalty": config.get("metadata_penalty", ""),
        "same_law_coherence": config.get("same_law_coherence", ""),
        "too_many_selected_cases_after_tightening": summary.get("too_many_selected_cases_after_tightening", 0),
        "cases_reduced_selected_count": summary.get("cases_reduced_selected_count", 0),
        "cases_reduced_unique_law_count": summary.get("cases_reduced_unique_law_count", 0),
        "possible_recall_loss_cases": summary.get("possible_recall_loss_cases", 0),
        "explicit_multilaw_cases": summary.get("explicit_multilaw_cases", 0),
        "avg_selected_count_before": _distribution_average(summary.get("baseline_selected_count_distribution")),
        "avg_selected_count_after": _distribution_average(summary.get("tightened_selected_count_distribution")),
        "avg_unique_law_count_before": _distribution_average(summary.get("baseline_unique_law_count_distribution")),
        "avg_unique_law_count_after": _distribution_average(summary.get("tightened_unique_law_count_distribution")),
        "selected_count_distribution_after": json.dumps(summary.get("tightened_selected_count_distribution", {}), ensure_ascii=False, sort_keys=True),
        "unique_law_count_distribution_after": json.dumps(summary.get("tightened_unique_law_count_distribution", {}), ensure_ascii=False, sort_keys=True),
        "p6r5_too_many_cases_with_original_count_12": summary.get("p6r5_too_many_cases_with_original_count_12", 0),
    }


def _distribution_average(distribution: Any) -> float:
    if not isinstance(distribution, Mapping):
        return 0.0
    total_count = sum(_safe_int(value) for value in distribution.values())
    if total_count <= 0:
        return 0.0
    total_value = sum(_safe_int(key) * _safe_int(value) for key, value in distribution.items())
    return round(total_value / total_count, 3)
