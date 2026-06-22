from __future__ import annotations

import csv
import json
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import polars as pl

TRIGGER_COLUMNS = (
    "selected_contains_khong_so",
    "selected_contains_old_code_or_legacy_doc",
    "version_overlap_suspected",
    "needs_canonical_metadata_cleanup",
    "needs_retrieval_filtering",
)

REPORT_FILES = {
    "report": "canonical_legacy_metadata_report.csv",
    "by_article": "canonical_legacy_grouped_by_article.csv",
    "by_law": "canonical_legacy_grouped_by_law.csv",
    "summary": "canonical_legacy_cleanup_summary.json",
    "plan": "canonical_legacy_cleanup_plan.md",
    "retrieval_rules": "candidate_retrieval_filter_rules.json",
    "metadata_rules": "candidate_metadata_cleanup_rules.json",
}

REPORT_COLUMNS = [
    "question_id", "question", "article_id", "law_id", "law_title", "article_no",
    "source_url", "domain", "status", "family", "anomaly_categories",
    "recommended_action", "evidence", "appears_in_answer", "selected_rank_if_available",
    "selected_count_for_question", "has_modern_same_family_in_question",
    "modern_same_family_law_ids", "legacy_same_family_law_ids",
]

GROUPED_ARTICLE_COLUMNS = [
    "article_id", "law_id", "law_title", "article_no", "family", "question_count",
    "anomaly_categories", "recommended_action", "source_url", "domain", "status",
]

GROUPED_LAW_COLUMNS = [
    "law_id", "law_title", "family", "question_count", "article_count",
    "anomaly_categories", "recommended_action", "sample_article_ids",
]

OLD_LAW_IDS = {"58-L/CTN", "33/2005/QH11", "10/2012/QH13", "36/2005/QH11", "50/2005/QH11"}
ACTION_PRIORITY = {
    "manual_review_required": 5,
    "canonical_metadata_cleanup_candidate": 4,
    "exact_alias_mapping_candidate": 3,
    "retrieval_filter_candidate": 2,
    "keep_no_action": 1,
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "x"}


def _normalize_key(value: Any) -> str:
    text = unicodedata.normalize("NFC", _text(value)).lower()
    return re.sub(r"\s+", " ", text).strip()


def _strip_accents(value: Any) -> str:
    text = unicodedata.normalize("NFD", _text(value).lower())
    text = text.replace("đ", "d")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def contains_khong_so(*values: Any) -> bool:
    return any("khong so" in _strip_accents(value) or "không số" in _text(value).lower() for value in values)


def parse_article_id(article_id: Any) -> dict[str, str]:
    parts = _text(article_id).split("|")
    if len(parts) >= 3:
        return {"law_id": parts[0].strip(), "law_title": parts[1].strip(), "article_no": "|".join(parts[2:]).strip()}
    return {"law_id": "", "law_title": "", "article_no": ""}


def _maybe_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "[{":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def parse_selected_articles(value: Any) -> list[dict[str, Any]]:
    value = _maybe_json(value)
    if value is None or value == "":
        return []
    if isinstance(value, dict):
        value = value.get("selected_articles") or value.get("articles") or []
    if isinstance(value, str):
        value = [part.strip() for part in value.split(";") if part.strip()]
    if not isinstance(value, list):
        return []
    parsed: list[dict[str, Any]] = []
    for idx, item in enumerate(value, start=1):
        if isinstance(item, str):
            article_id = item.strip()
            parsed.append({"article_id": article_id, "rank": idx, **parse_article_id(article_id)})
            continue
        if not isinstance(item, dict):
            continue
        article_id = _text(item.get("article_id") or item.get("legal_article_id") or item.get("id") or item.get("canonical_article_id"))
        law_id = _text(item.get("law_id"))
        law_title = _text(item.get("law_title"))
        article_no = _text(item.get("article_no"))
        if article_id and (not law_id or not law_title or not article_no):
            parsed_id = parse_article_id(article_id)
            law_id = law_id or parsed_id["law_id"]
            law_title = law_title or parsed_id["law_title"]
            article_no = article_no or parsed_id["article_no"]
        if not article_id and law_id and law_title and article_no:
            article_id = f"{law_id}|{law_title}|{article_no}"
        if article_id:
            parsed.append({"article_id": article_id, "law_id": law_id, "law_title": law_title, "article_no": article_no, "rank": item.get("rank") or item.get("selected_rank") or idx})
    return parsed


def detect_family(law_id: Any, law_title: Any) -> str:
    text = _strip_accents(f"{law_id} {law_title}")
    if "bo luat lao dong" in text:
        return "Bộ luật Lao động"
    if "bo luat dan su" in text:
        return "Bộ luật Dân sự"
    if "luat thuong mai" in text:
        return "Luật Thương mại"
    if "so huu tri tue" in text:
        return "Luật Sở hữu trí tuệ"
    if "luat doanh nghiep" in text:
        return "Luật Doanh nghiệp"
    if "quan ly thue" in text:
        return "Luật Quản lý thuế"
    if "nghi dinh" in text and "lao dong" in text and ("phat" in text or "xu phat" in text):
        return "Nghị định xử phạt lao động"
    if ("nghi dinh" in text or "thong tu" in text) and "thue" in text:
        return "Nghị định/Thông tư thuế"
    return "Other"


def _extract_year(value: Any) -> int | None:
    match = re.search(r"/(19\d{2}|20\d{2})/", _text(value))
    return int(match.group(1)) if match else None


def _is_old_decree_or_circular(law_id: str, law_title: str) -> bool:
    year = _extract_year(law_id)
    text = _strip_accents(law_title)
    return bool(year and year < 2015 and ("nghi dinh" in text or "thong tu" in text))


def _is_legacy_signal(law_id: str, law_title: str) -> bool:
    return contains_khong_so(law_id, law_title) or law_id in OLD_LAW_IDS


def _is_modern_signal(law_id: str, law_title: str) -> bool:
    year = _extract_year(law_id)
    return bool(law_id and not _is_legacy_signal(law_id, law_title) and (year is None or year >= 2015))


def _has_duplicate_law_type_or_id(law_id: str, law_title: str) -> bool:
    folded = _strip_accents(law_title)
    return bool((law_id and folded.count(_strip_accents(law_id)) > 1) or re.search(r"\b(luat|bo luat|nghi dinh|thong tu)\b.*\b\1\b", folded))


def _has_suspicious_title_normalization(law_title: str) -> bool:
    folded = _strip_accents(law_title)
    return " khong so" in folded or " so so" in folded or "  " in law_title


def _detect_anomalies(
    *,
    law_id: str,
    law_title: str,
    source_url: str,
    status: str,
    found_in_canonical: bool,
    residual_row: dict[str, Any],
    has_modern_same_family: bool,
    has_legacy_same_family: bool,
) -> list[str]:
    categories: list[str] = []
    if not found_in_canonical:
        categories.append("selected_article_not_found_in_canonical")
    if not law_id:
        categories.append("law_id_empty")
    if contains_khong_so(law_id):
        categories.append("law_id_khong_so")
    if contains_khong_so(law_title):
        categories.append("law_title_contains_khong_so")
    if re.search(r"\bsố\s*$", law_title, flags=re.IGNORECASE):
        categories.append("law_title_trailing_so")
    if _has_duplicate_law_type_or_id(law_id, law_title):
        categories.append("law_title_duplicate_law_type_or_law_id")
    if _has_suspicious_title_normalization(law_title):
        categories.append("law_title_suspicious_normalization")
    if _truthy(residual_row.get("selected_contains_old_code_or_legacy_doc")) or law_id in OLD_LAW_IDS:
        categories.append("old_code_or_legacy_doc")
    if has_modern_same_family and has_legacy_same_family:
        categories.append("modern_and_legacy_overlap_same_question")
    if _truthy(residual_row.get("version_overlap_suspected")):
        categories.append("title_mismatch_suspected")
    if not source_url:
        categories.append("source_url_missing")
    if not status or _normalize_key(status) in {"unknown", "khong ro", "không rõ", "none", "nan"}:
        categories.append("status_missing_or_unknown")
    return categories


def _recommend_action(
    *,
    law_id: str,
    law_title: str,
    article_no: str,
    found_in_canonical: bool,
    anomalies: list[str],
    has_modern_same_family: bool,
    same_family_official_same_article_no: bool,
) -> str:
    if not found_in_canonical:
        return "manual_review_required"
    if contains_khong_so(law_id, law_title):
        if same_family_official_same_article_no and article_no:
            return "exact_alias_mapping_candidate"
        return "canonical_metadata_cleanup_candidate"
    if (law_id in OLD_LAW_IDS or "old_code_or_legacy_doc" in anomalies or _is_old_decree_or_circular(law_id, law_title)) and has_modern_same_family:
        return "retrieval_filter_candidate"
    if "law_title_suspicious_normalization" in anomalies or "law_title_trailing_so" in anomalies:
        return "canonical_metadata_cleanup_candidate"
    if "status_missing_or_unknown" in anomalies or "source_url_missing" in anomalies:
        return "manual_review_required"
    return "keep_no_action"


def _best_action(actions: list[str] | set[str]) -> str:
    if not actions:
        return "keep_no_action"
    return max(actions, key=lambda action: ACTION_PRIORITY.get(action, 0))


def _appears_in_answer(answer: str, law_id: str, law_title: str, article_no: str) -> bool:
    answer_norm = _normalize_key(answer)
    return bool((law_id and _normalize_key(law_id) in answer_norm) or (article_no and _normalize_key(article_no) in answer_norm) or (law_title and _normalize_key(law_title) in answer_norm))


def _load_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _load_jsonl_by_id(path: str | Path) -> dict[str, dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            row_id = _text(row.get("id") or row.get("question_id"))
            if row_id:
                records[row_id] = row
    return records


def _load_csv_by_id(path: str | Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in _load_csv_rows(path):
        row_id = _text(row.get("id") or row.get("question_id"))
        if row_id:
            out[row_id] = row
    return out


def _load_canonical_articles(path: str | Path) -> dict[str, dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return {}
    wanted = ["article_id", "law_id", "law_title", "article_no", "article_title", "source_url", "domain", "status"]
    try:
        schema = pl.scan_parquet(p).collect_schema()
        available = set(schema.names() if hasattr(schema, "names") else schema.keys())
    except Exception:
        available = set(pl.read_parquet(p, n_rows=0).columns)
    columns = [name for name in wanted if name in available]
    df = pl.read_parquet(p, columns=columns)
    for name in wanted:
        if name not in df.columns:
            df = df.with_columns(pl.lit("").alias(name))
    return {str(row["article_id"]): dict(row) for row in df.iter_rows(named=True)}


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def _joined(values: list[str] | set[str]) -> str:
    return "; ".join(sorted({v for v in values if v}))


def _split_list_field(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def build_candidate_retrieval_filter_rules() -> dict[str, Any]:
    return {
        "enabled_by_default": False,
        "rules": [
            {"id": "legacy_same_family_overlap_filter", "enabled": False, "description": "Demote legacy candidates only when a modern same-family candidate appears and the question does not ask for the old version."},
            {"id": "khong_so_candidate_quarantine", "enabled": False, "description": "Quarantine canonical candidates whose law_id or law_title contains Không số pending metadata repair."},
            {"id": "old_decree_circular_modern_overlap_demote", "enabled": False, "description": "Demote pre-2015 decree/circular candidates only with modern same-family overlap."},
        ],
    }


def build_candidate_metadata_cleanup_rules() -> dict[str, Any]:
    return {
        "enabled_by_default": False,
        "display_only": True,
        "rules": [
            {"id": "display_remove_khong_so_placeholder", "enabled": False, "display_only": True, "description": "Hide placeholder Không số in answer-facing citation display while preserving canonical article_id."},
            {"id": "display_trim_trailing_so", "enabled": False, "display_only": True, "description": "Trim dangling 'số' suffix from malformed law titles in display output only."},
            {"id": "candidate_alias_same_family_same_article_no", "enabled": False, "display_only": True, "description": "Suggest an alias when Không số and official law_id share family and article number."},
        ],
    }


def _filter_residual_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if any(_truthy(row.get(col)) for col in TRIGGER_COLUMNS)]


def _row_id(row: dict[str, Any]) -> str:
    return _text(row.get("id") or row.get("question_id"))


def _enrich_selected(item: dict[str, Any], canonical_articles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    article_id = _text(item.get("article_id"))
    canonical = canonical_articles.get(article_id, {})
    parsed = parse_article_id(article_id)
    law_id = _text(canonical.get("law_id") or item.get("law_id") or parsed["law_id"])
    law_title = _text(canonical.get("law_title") or item.get("law_title") or parsed["law_title"])
    article_no = _text(canonical.get("article_no") or item.get("article_no") or parsed["article_no"])
    return {
        "article_id": article_id,
        "law_id": law_id,
        "law_title": law_title,
        "article_no": article_no,
        "source_url": _text(canonical.get("source_url")),
        "domain": _text(canonical.get("domain")),
        "status": _text(canonical.get("status")),
        "rank": item.get("rank") or "",
        "family": detect_family(law_id, law_title),
        "found_in_canonical": bool(canonical),
    }


def _evidence_for_row(anomalies: list[str], residual: dict[str, Any]) -> str:
    bits = list(anomalies)
    for col in TRIGGER_COLUMNS:
        if _truthy(residual.get(col)):
            bits.append(f"residual:{col}")
    return _joined(bits)


def build_canonical_legacy_cleanup_plan(
    residual_report_path: str | Path,
    low_confidence_path: str | Path,
    retrieval_results_path: str | Path,
    answers_path: str | Path,
    canonical_articles_path: str | Path,
    output_dir: str | Path,
    canonical_documents_path: str | Path | None = None,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    if output_path.exists():
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    residual_rows = _filter_residual_rows(_load_csv_rows(residual_report_path))
    low_by_id = _load_csv_by_id(low_confidence_path)
    retrieval_by_id = _load_jsonl_by_id(retrieval_results_path)
    answers_by_id = _load_jsonl_by_id(answers_path)
    canonical_articles = _load_canonical_articles(canonical_articles_path)
    report_rows: list[dict[str, Any]] = []

    for residual in residual_rows:
        question_id = _row_id(residual)
        retrieval = retrieval_by_id.get(question_id, {})
        selected = parse_selected_articles(retrieval.get("selected_articles") or retrieval.get("selected_article_ids") or residual.get("selected_articles"))
        enriched = [_enrich_selected(item, canonical_articles) for item in selected]
        family_modern: dict[str, set[str]] = defaultdict(set)
        family_legacy: dict[str, set[str]] = defaultdict(set)
        family_article_nos: dict[tuple[str, str], set[str]] = defaultdict(set)
        for item in enriched:
            family = item["family"]
            law_id = item["law_id"]
            law_title = item["law_title"]
            article_no = item["article_no"]
            if _is_modern_signal(law_id, law_title):
                family_modern[family].add(law_id)
            if _is_legacy_signal(law_id, law_title) or _is_old_decree_or_circular(law_id, law_title):
                family_legacy[family].add(law_id)
            if law_id and article_no and not contains_khong_so(law_id, law_title):
                family_article_nos[(family, article_no)].add(law_id)

        question = _text(residual.get("question") or low_by_id.get(question_id, {}).get("question") or retrieval.get("question"))
        answer = _text(answers_by_id.get(question_id, {}).get("answer"))
        for item in enriched:
            family = item["family"]
            law_id = item["law_id"]
            law_title = item["law_title"]
            article_no = item["article_no"]
            has_modern_same_family = bool(family_modern.get(family))
            has_legacy_same_family = bool(family_legacy.get(family))
            same_family_official_same_article_no = bool(family_article_nos.get((family, article_no)))
            anomalies = _detect_anomalies(
                law_id=law_id,
                law_title=law_title,
                source_url=item["source_url"],
                status=item["status"],
                found_in_canonical=item["found_in_canonical"],
                residual_row=residual,
                has_modern_same_family=has_modern_same_family,
                has_legacy_same_family=has_legacy_same_family,
            )
            action = _recommend_action(
                law_id=law_id,
                law_title=law_title,
                article_no=article_no,
                found_in_canonical=item["found_in_canonical"],
                anomalies=anomalies,
                has_modern_same_family=has_modern_same_family,
                same_family_official_same_article_no=same_family_official_same_article_no,
            )
            report_rows.append({
                "question_id": question_id,
                "question": question,
                "article_id": item["article_id"],
                "law_id": law_id,
                "law_title": law_title,
                "article_no": article_no,
                "source_url": item["source_url"],
                "domain": item["domain"],
                "status": item["status"],
                "family": family,
                "anomaly_categories": _joined(anomalies),
                "recommended_action": action,
                "evidence": _evidence_for_row(anomalies, residual),
                "appears_in_answer": _appears_in_answer(answer, law_id, law_title, article_no),
                "selected_rank_if_available": item["rank"],
                "selected_count_for_question": len(enriched),
                "has_modern_same_family_in_question": has_modern_same_family,
                "modern_same_family_law_ids": _joined(family_modern.get(family, set())),
                "legacy_same_family_law_ids": _joined(family_legacy.get(family, set())),
            })

    grouped_article_rows = _group_by_article(report_rows)
    grouped_law_rows = _group_by_law(report_rows)
    summary = _build_summary(
        residual_rows=residual_rows,
        report_rows=report_rows,
        grouped_article_rows=grouped_article_rows,
        grouped_law_rows=grouped_law_rows,
        canonical_documents_path=canonical_documents_path,
    )
    _write_csv(output_path / REPORT_FILES["report"], report_rows, REPORT_COLUMNS)
    _write_csv(output_path / REPORT_FILES["by_article"], grouped_article_rows, GROUPED_ARTICLE_COLUMNS)
    _write_csv(output_path / REPORT_FILES["by_law"], grouped_law_rows, GROUPED_LAW_COLUMNS)
    (output_path / REPORT_FILES["summary"]).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_path / REPORT_FILES["plan"]).write_text(_build_markdown_plan(summary), encoding="utf-8")
    (output_path / REPORT_FILES["retrieval_rules"]).write_text(json.dumps(build_candidate_retrieval_filter_rules(), ensure_ascii=False, indent=2), encoding="utf-8")
    (output_path / REPORT_FILES["metadata_rules"]).write_text(json.dumps(build_candidate_metadata_cleanup_rules(), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "completed", "output_dir": str(output_path), "files": {name: str(output_path / filename) for name, filename in REPORT_FILES.items()}, **summary}


def _group_by_article(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["article_id"]].append(row)
    out: list[dict[str, Any]] = []
    for article_id, items in grouped.items():
        first = items[0]
        anomalies: set[str] = set()
        actions: list[str] = []
        question_ids: set[str] = set()
        for item in items:
            question_ids.add(item["question_id"])
            actions.append(item["recommended_action"])
            anomalies.update(_split_list_field(item.get("anomaly_categories")))
        out.append({"article_id": article_id, "law_id": first["law_id"], "law_title": first["law_title"], "article_no": first["article_no"], "family": first["family"], "question_count": len(question_ids), "anomaly_categories": _joined(anomalies), "recommended_action": _best_action(actions), "source_url": first["source_url"], "domain": first["domain"], "status": first["status"]})
    return sorted(out, key=lambda row: (-int(row["question_count"]), row["article_id"]))


def _group_by_law(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["law_id"], row["law_title"])].append(row)
    out: list[dict[str, Any]] = []
    for (law_id, law_title), items in grouped.items():
        first = items[0]
        anomalies: set[str] = set()
        actions: list[str] = []
        question_ids: set[str] = set()
        article_ids: set[str] = set()
        for item in items:
            question_ids.add(item["question_id"])
            article_ids.add(item["article_id"])
            actions.append(item["recommended_action"])
            anomalies.update(_split_list_field(item.get("anomaly_categories")))
        out.append({"law_id": law_id, "law_title": law_title, "family": first["family"], "question_count": len(question_ids), "article_count": len(article_ids), "anomaly_categories": _joined(anomalies), "recommended_action": _best_action(actions), "sample_article_ids": _joined(list(sorted(article_ids))[:10])})
    return sorted(out, key=lambda row: (-int(row["question_count"]), row["law_id"], row["law_title"]))


def _build_summary(
    *,
    residual_rows: list[dict[str, Any]],
    report_rows: list[dict[str, Any]],
    grouped_article_rows: list[dict[str, Any]],
    grouped_law_rows: list[dict[str, Any]],
    canonical_documents_path: str | Path | None,
) -> dict[str, Any]:
    anomaly_counter: Counter[str] = Counter()
    samples: dict[str, list[str]] = defaultdict(list)
    for row in report_rows:
        for category in _split_list_field(row.get("anomaly_categories")):
            anomaly_counter[category] += 1
            qid = row["question_id"]
            if len(samples[category]) < 10 and qid not in samples[category]:
                samples[category].append(qid)
    action_counter = Counter(row["recommended_action"] for row in report_rows)
    family_counter = Counter(row["family"] for row in report_rows)
    law_id_counter = Counter(row["law_id"] for row in report_rows)
    law_title_counter = Counter(row["law_title"] for row in report_rows)
    article_counter = Counter(row["article_id"] for row in report_rows)
    khong_so_rows = [row for row in report_rows if contains_khong_so(row["law_id"], row["law_title"])]
    legacy_overlap_question_ids = {row["question_id"] for row in report_rows if "modern_and_legacy_overlap_same_question" in _split_list_field(row.get("anomaly_categories"))}
    return {
        "total_residual_rows": len(residual_rows),
        "total_selected_article_refs_scanned": len(report_rows),
        "unique_selected_article_ids": len({row["article_id"] for row in report_rows}),
        "anomaly_category_counts": dict(anomaly_counter.most_common()),
        "recommended_action_counts": dict(action_counter.most_common()),
        "top_law_ids": _top_counter(law_id_counter),
        "top_law_titles": _top_counter(law_title_counter),
        "top_article_ids": _top_counter(article_counter),
        "family_counts": dict(family_counter.most_common()),
        "khong_so_article_count": len({row["article_id"] for row in khong_so_rows}),
        "khong_so_question_count": len({row["question_id"] for row in khong_so_rows}),
        "legacy_overlap_question_count": len(legacy_overlap_question_ids),
        "canonical_join_missing_count": anomaly_counter.get("selected_article_not_found_in_canonical", 0),
        "safe_cleanup_candidate_count": action_counter.get("canonical_metadata_cleanup_candidate", 0) + action_counter.get("exact_alias_mapping_candidate", 0),
        "retrieval_filter_candidate_count": action_counter.get("retrieval_filter_candidate", 0),
        "manual_review_required_count": action_counter.get("manual_review_required", 0),
        "sample_ids_by_category": dict(samples),
        "canonical_documents_supplied": bool(canonical_documents_path and Path(canonical_documents_path).exists()),
        "grouped_article_rows": len(grouped_article_rows),
        "grouped_law_rows": len(grouped_law_rows),
        "final_recommendation": _final_recommendation(action_counter, anomaly_counter),
    }


def _top_counter(counter: Counter[str], limit: int = 20) -> list[dict[str, Any]]:
    return [{"value": value, "count": count} for value, count in counter.most_common(limit)]


def _final_recommendation(action_counter: Counter[str], anomaly_counter: Counter[str]) -> str:
    if action_counter.get("retrieval_filter_candidate", 0) > action_counter.get("canonical_metadata_cleanup_candidate", 0):
        return "Run a controlled retrieval-time legacy filter experiment before Phase 7; keep all rules disabled until validated."
    if anomaly_counter.get("law_id_khong_so", 0) or anomaly_counter.get("law_title_contains_khong_so", 0):
        return "Prioritize display-only canonical metadata cleanup and alias planning, then re-run error analysis before Phase 7."
    if action_counter.get("manual_review_required", 0):
        return "Manual review is needed before changing retrieval defaults."
    return "No irreversible cleanup recommended; keep P6.R9 as diagnostic evidence."


def _markdown_counter(counter: dict[str, int]) -> str:
    if not counter:
        return "- No family counts generated."
    return "\n".join(f"- {key}: {value}" for key, value in counter.items())


def _build_markdown_plan(summary: dict[str, Any]) -> str:
    return f"""# P6.R9 Canonical Legacy Metadata Cleanup Plan

## Executive summary

P6.R9 scanned {summary['total_residual_rows']} residual rows and {summary['total_selected_article_refs_scanned']} selected article references. It found {summary['khong_so_article_count']} unique Không số article references, {summary['legacy_overlap_question_count']} questions with modern/legacy same-family overlap, and {summary['canonical_join_missing_count']} selected references missing from canonical article metadata.

## What was fixed by P6.R8a

P6.R8a reduced answer-facing legacy display noise by patching generated answers. That was useful as a containment step, but it did not change canonical article metadata or retrieval candidate selection.

## What remains

The remaining problems are metadata and retrieval-candidate quality issues: malformed law identifiers/titles, possible old-version overlap in selected sets, and some missing canonical joins. These should be handled before escalating to Phase 7 reranking.

## Why not continue answer patching

More answer patching would hide symptoms after retrieval and generation. The safer next move is to diagnose canonical metadata and candidate selection sources, then apply disabled-by-default cleanup or filter rules in a controlled experiment.

## Top problematic law families

{_markdown_counter(summary.get('family_counts', {}))}

## Proposed cleanup options

1. Metadata display cleanup layer only: keep canonical IDs unchanged, but hide placeholders such as Không số in answer-facing citation display.
2. Retrieval-time legacy filter: demote legacy candidates only when a modern same-family candidate appears in the same selected set and the question does not explicitly ask for the legacy version.
3. Canonical alias mapping: create candidate aliases for same-family, same-article-number pairs, but do not rewrite canonical parquet directly.
4. Full canonical corpus rebuild or repair: defer until diagnostic reports prove that metadata corruption is systemic and reproducible.

## Recommended next task

{summary['final_recommendation']}

## Risks and rollback notes

All candidate rules emitted by P6.R9 are disabled by default. Rollback is simply deleting the generated P6.R9 output directory or ignoring its candidate rule files. No retrieval results, answers, or canonical parquet files are modified by this task.
"""



