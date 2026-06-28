
"""LLM-based verifier for legal article citations in submission records."""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

PROMPT_PATH = Path("backend/prompts/article_verifier_prompt.txt")
REQUIRED_FIELDS = {"id", "question", "answer", "relevant_docs", "relevant_articles"}
VALID_MODES = {"strict", "balanced", "recall"}
SELECTED_LABEL_ORDER = {"direct_relevant": 0, "strong_supporting": 1, "weak_supporting": 2}
CONFLICT_GROUPS = (("78/2006/QH11", "38/2019/QH14"), ("43/2013/QH13", "22/2023/QH15"), ("39/2018/NĐ-CP", "80/2021/NĐ-CP"), ("95/2013/NĐ-CP", "12/2022/NĐ-CP"))
LOCAL_PATTERNS = ("nq-hdnd", "qd-ubnd", "ubnd", "hdnd")
LOCAL_INDICATORS = ("tinh", "thanh pho", "huyen", "xa", "dia ban", "ha noi", "tp. ho chi minh", "ho chi minh", "da nang", "hai phong", "can tho", "binh duong", "dong nai", "khanh hoa", "lang son", "thua thien hue", "vinh long", "hau giang", "dong thap", "binh dinh", "vinh phuc")
SINGLE_FACT_MARKERS = ("bao lau", "may ngay", "ty le", "muc phat", "thoi han", "ai bi xu phat")
LIST_POLICY_MARKERS = ("nhung gi", "bao gom", "cac truong hop", "dieu kien", "ho so", "thu tuc", "quy trinh", "chinh sach", "muc phat", "bien phap khac phuc", "quyen va nghia vu")
MULTI_PART_MARKERS = ("dong thoi", "va neu", "trong khi", "cung luc", "mat khac")
DOMAIN_KEYWORDS = {
    "tax": ("thue", "khai thue", "nop thue", "tien cham nop", "le phi mon bai", "hoa don"),
    "labor_social_insurance": ("lao dong", "nguoi lao dong", "bao hiem xa hoi", "bhxh", "bao hiem that nghiep", "hop dong lao dong"),
    "sme_support": ("doanh nghiep nho va vua", "dnnvv", "ho tro doanh nghiep", "khoi nghiep sang tao"),
    "bidding": ("dau thau", "nha thau", "goi thau", "ho so du thau", "lua chon nha thau"),
    "accounting": ("ke toan", "bao cao tai chinh", "so ke toan", "chung tu ke toan"),
    "business_registration": ("dang ky doanh nghiep", "ho kinh doanh", "ma so doanh nghiep", "thanh lap doanh nghiep"),
    "consumer_data_ip": ("du lieu ca nhan", "bao ve nguoi tieu dung", "so huu tri tue", "nhan hieu", "ban quyen"),
    "commerce_contract": ("hop dong", "thuong mai", "mua ban hang hoa", "dich vu", "dai ly thuong mai"),
}

@dataclass(frozen=True)
class ArticleRef:
    raw: str
    law_id: str
    law_title: str
    article_no: str
    @property
    def doc_ref(self) -> str:
        return f"{self.law_id}|{self.law_title}"

@dataclass(frozen=True)
class ArticleTextLookup:
    exact: dict[str, str]
    fallback: dict[tuple[str, str], list[tuple[str, str]]]

@dataclass(frozen=True)
class Candidate:
    candidate_id: int
    ref: ArticleRef
    article_text: str
    original_index: int
    missing_article_text: bool = False
    warning: str | None = None

@dataclass(frozen=True)
class Decision:
    candidate_id: int
    label: str
    confidence: float
    reason: str

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify submission articles with a local OpenAI-compatible LLM.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--fallback-pruned", required=True)
    parser.add_argument("--articles-parquet", required=True)
    parser.add_argument("--audit-by-record", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--changes", required=True)
    parser.add_argument("--zip-output", default=None)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--mode", choices=sorted(VALID_MODES), default="balanced")
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--max-article-chars", type=int, default=1200)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--disable-thinking", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-id", type=int, default=None)
    parser.add_argument("--end-id", type=int, default=None)
    parser.add_argument("--only-possible-overpruned", action="store_true")
    parser.add_argument("--priority-domains", default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--prompt-path", default=str(PROMPT_PATH))
    return parser

def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_records = load_submission(args.input)
    fallback_records = load_submission(args.fallback_pruned)
    fallback_by_id = {record["id"]: record for record in fallback_records}
    audit_by_id = load_audit_by_record(args.audit_by_record)
    article_lookup = load_article_text_lookup(args.articles_parquet)
    prompt_template = Path(args.prompt_path).read_text(encoding="utf-8")
    output_records, report, changes = verify_submission(
        input_records=input_records,
        fallback_by_id=fallback_by_id,
        audit_by_id=audit_by_id,
        article_lookup=article_lookup,
        prompt_template=prompt_template,
        options=vars(args),
        llm_client=lambda messages: call_openai_compatible(args.base_url, args.model, messages, args.temperature, args.timeout, disable_thinking=args.disable_thinking),
    )
    write_json(args.output, output_records)
    write_json(args.report, report)
    write_jsonl(args.changes, changes)
    if args.zip_output:
        write_flat_zip(args.zip_output, output_records)
    return 0

def verify_submission(*, input_records: list[dict[str, Any]], fallback_by_id: dict[int, dict[str, Any]], audit_by_id: dict[int, dict[str, Any]], article_lookup: ArticleTextLookup, prompt_template: str, options: dict[str, Any], llm_client: Callable[[list[dict[str, str]]], str]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    output: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    selected_label_counts: Counter[str] = Counter()
    rejected_label_counts: Counter[str] = Counter()
    processed_domains: Counter[str] = Counter()
    fallback_domains: Counter[str] = Counter()
    domain_stats: dict[str, Counter[str]] = defaultdict(Counter)
    processed_count = 0
    for record in input_records:
        record_id = int(record["id"])
        fallback = fallback_by_id.get(record_id) or fallback_from_original(record)
        audit = audit_by_id.get(record_id, {})
        domain = str(audit.get("domain") or detect_domain(record.get("question", ""), record.get("answer", "")))
        question_type = detect_question_type(str(record.get("question") or ""))
        if not should_process_record(record, audit, options, processed_count):
            patched = clone_submission_record(fallback)
            ensure_non_empty_refs(patched, record)
            output.append(patched)
            fallback_domains[domain] += 1
            changes.append(build_change(record, patched, mode=options["mode"], domain=domain, question_type=question_type, possible_overpruned=parse_bool(audit.get("possible_overpruned")), llm_success=False, fallback_used=True, warnings=["not processed; used fallback-pruned record"]))
            continue
        processed_count += 1
        processed_domains[domain] += 1
        try:
            patched, change = verify_record(record=record, fallback=fallback, audit=audit, article_lookup=article_lookup, prompt_template=prompt_template, options=options, llm_client=llm_client, domain=domain, question_type=question_type)
        except Exception as exc:
            patched = clone_submission_record(fallback)
            ensure_non_empty_refs(patched, record)
            change = build_change(record, patched, mode=options["mode"], domain=domain, question_type=question_type, possible_overpruned=parse_bool(audit.get("possible_overpruned")), llm_success=False, fallback_used=True, warnings=[f"exception fallback: {exc}"])
            change["_counters"] = {"llm_failure_count": 1, "fallback_count": 1}
        counters.update(change.pop("_counters", {}))
        selected_label_counts.update(change.get("selected_labels", []))
        rejected_label_counts.update(change.get("rejected_labels", []))
        if change.get("fallback_used"):
            fallback_domains[domain] += 1
            domain_stats[domain]["fallback"] += 1
        domain_stats[domain]["processed"] += int(not change.get("fallback_used") or change.get("llm_success"))
        domain_stats[domain]["selected"] += len(change.get("selected_labels", []))
        domain_stats[domain]["rejected"] += len(change.get("rejected_labels", []))
        domain_stats[domain]["articles_after"] += len(patched["relevant_articles"])
        output.append(patched)
        changes.append(change)
        if float(options.get("sleep_seconds") or 0) > 0:
            time.sleep(float(options["sleep_seconds"]))
    report = build_report(input_records, output, changes, counters, selected_label_counts, rejected_label_counts, processed_domains, fallback_domains, domain_stats, options)
    return output, report, changes

def verify_record(*, record: dict[str, Any], fallback: dict[str, Any], audit: dict[str, Any], article_lookup: ArticleTextLookup, prompt_template: str, options: dict[str, Any], llm_client: Callable[[list[dict[str, str]]], str], domain: str, question_type: str) -> tuple[dict[str, Any], dict[str, Any]]:
    warnings: list[str] = []
    counters: Counter[str] = Counter()
    refs = order_candidate_refs(record.get("relevant_articles") or [], fallback.get("relevant_articles") or [], audit, int(options["max_candidates"]))
    candidates: list[Candidate] = []
    for index, ref in enumerate(refs):
        text, warning, missing = lookup_article_text(article_lookup, ref)
        if warning:
            warnings.append(warning)
        if missing:
            counters["missing_article_text_count"] += 1
        candidates.append(Candidate(index + 1, ref, text[: int(options["max_article_chars"])], index, missing, warning))
    messages = build_messages(prompt_template, str(record["question"]), candidates)
    try:
        parsed = parse_llm_json(llm_client(messages))
        counters["llm_success_count"] += 1
    except Exception as exc:
        counters["llm_failure_count"] += 1
        counters["json_parse_failure_count"] += 1
        patched = fallback_or_top_original(record, fallback)
        change = build_change(record, patched, mode=options["mode"], domain=domain, question_type=question_type, possible_overpruned=parse_bool(audit.get("possible_overpruned")), llm_success=False, fallback_used=True, warnings=warnings + [f"LLM/JSON failure fallback: {exc}"])
        change["_counters"] = {**counters, "fallback_count": 1}
        return patched, change
    decisions, invalid_count = parse_decisions(parsed)
    counters["invalid_candidate_id_count"] += invalid_count
    selected, rejected = postprocess_decisions(decisions, candidates, mode=str(options["mode"]), question_type=question_type, question=str(record["question"]))
    counters["selected_articles_count"] += len(selected)
    counters["rejected_articles_count"] += len(rejected)
    if not selected:
        counters["empty_selection_fallback_count"] += 1
        patched = fallback_or_top_original(record, fallback)
        change = build_change(record, patched, mode=options["mode"], domain=domain, question_type=question_type, possible_overpruned=parse_bool(audit.get("possible_overpruned")), llm_success=True, fallback_used=True, warnings=warnings + ["empty valid selection; used fallback-pruned record"])
        change["selected_labels"] = [decision.label for decision, _ in selected]
        change["rejected_labels"] = [decision.label for decision, _ in rejected]
        change["missing_article_text_refs"] = [candidate.ref.raw for candidate in candidates if candidate.missing_article_text]
        change["_counters"] = {**counters, "fallback_count": 1}
        return patched, change
    articles = [candidate.ref.raw for _, candidate in selected]
    patched = clone_submission_record(record)
    patched["relevant_articles"] = articles
    patched["relevant_docs"] = rebuild_docs_from_articles(articles)
    ensure_non_empty_refs(patched, record)
    change = build_change(record, patched, mode=options["mode"], domain=domain, question_type=question_type, possible_overpruned=parse_bool(audit.get("possible_overpruned")), llm_success=True, fallback_used=False, warnings=warnings)
    change["selected_labels"] = [decision.label for decision, _ in selected]
    change["rejected_labels"] = [decision.label for decision, _ in rejected]
    change["missing_article_text_refs"] = [candidate.ref.raw for candidate in candidates if candidate.missing_article_text]
    change["_counters"] = dict(counters)
    return patched, change

def postprocess_decisions(decisions: list[Decision], candidates: list[Candidate], *, mode: str, question_type: str, question: str) -> tuple[list[tuple[Decision, Candidate]], list[tuple[Decision, Candidate]]]:
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    selected: list[tuple[Decision, Candidate]] = []
    rejected: list[tuple[Decision, Candidate]] = []
    asks_old_law = question_explicitly_asks_old_law(question)
    has_local = has_local_indicator(question)
    for decision in decisions:
        candidate = candidate_by_id.get(decision.candidate_id)
        if candidate is None:
            continue
        if decision.label == "superseded_old_law" and not asks_old_law:
            rejected.append((decision, candidate)); continue
        if decision.label == "local_only_irrelevant" and not has_local:
            rejected.append((decision, candidate)); continue
        if passes_mode_threshold(decision.label, decision.confidence, mode=mode, question_type=question_type):
            selected.append((decision, candidate))
        else:
            rejected.append((decision, candidate))
    selected.sort(key=lambda pair: (SELECTED_LABEL_ORDER.get(pair[0].label, 99), pair[1].original_index))
    cap = cap_for_mode(mode, question_type)
    rejected.extend(selected[cap:])
    return selected[:cap], rejected

def passes_mode_threshold(label: str, confidence: float, *, mode: str, question_type: str) -> bool:
    if mode == "strict":
        return label == "direct_relevant" and confidence >= 0.75
    if mode == "balanced":
        if label in {"direct_relevant", "strong_supporting"}:
            return confidence >= 0.60
        return label == "weak_supporting" and confidence >= 0.70 and question_type in {"list_policy", "multi_part"}
    if mode == "recall":
        if label in {"direct_relevant", "strong_supporting"}:
            return confidence >= 0.50
        return label == "weak_supporting" and confidence >= 0.60 and question_type in {"list_policy", "multi_part"}
    return False

def cap_for_mode(mode: str, question_type: str) -> int:
    return {
        "strict": {"single_fact": 2, "default": 3, "list_policy": 4, "multi_part": 4},
        "balanced": {"single_fact": 3, "default": 4, "list_policy": 5, "multi_part": 6},
        "recall": {"single_fact": 4, "default": 5, "list_policy": 6, "multi_part": 7},
    }[mode][question_type]

def parse_llm_json(text: str) -> dict[str, Any]:
    text = strip_think_blocks(text)
    attempts = [text, strip_markdown_fences(text)]
    first, last = text.find("{"), text.rfind("}")
    if first >= 0 and last > first:
        extracted = text[first:last + 1]
        attempts.extend([extracted, strip_markdown_fences(extracted)])
    last_error: Exception | None = None
    for attempt in attempts:
        try:
            loaded = json.loads(attempt.strip())
            if isinstance(loaded, dict):
                return loaded
        except json.JSONDecodeError as exc:
            last_error = exc
    raise ValueError(f"could not parse LLM JSON: {last_error}")

def strip_think_blocks(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()

def strip_markdown_fences(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()

def parse_decisions(parsed: dict[str, Any]) -> tuple[list[Decision], int]:
    decisions: list[Decision] = []
    invalid = 0
    seen: set[int] = set()
    for section in ("selected", "rejected"):
        values = parsed.get(section) or []
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                invalid += 1; continue
            try:
                candidate_id = int(item.get("candidate_id"))
            except (TypeError, ValueError):
                invalid += 1; continue
            if candidate_id in seen:
                invalid += 1; continue
            seen.add(candidate_id)
            decisions.append(Decision(candidate_id, normalize_label(str(item.get("label") or "irrelevant")), clamp_confidence(item.get("confidence", 0)), str(item.get("reason") or "")))
    return decisions, invalid

def normalize_label(label: str) -> str:
    normalized = normalize_for_matching(label).replace(" ", "_")
    return {
        "direct": "direct_relevant", "directly_relevant": "direct_relevant", "direct_relevant": "direct_relevant",
        "supporting": "strong_supporting", "strong_supporting": "strong_supporting",
        "weak": "weak_supporting", "weak_supporting": "weak_supporting",
        "not_relevant": "irrelevant", "irrelevant": "irrelevant",
        "old_law": "superseded_old_law", "superseded": "superseded_old_law", "superseded_old_law": "superseded_old_law",
        "local_only_irrelevant": "local_only_irrelevant",
    }.get(normalized, "irrelevant")

def clamp_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))

def build_messages(prompt_template: str, question: str, candidates: list[Candidate]) -> list[dict[str, str]]:
    return [{"role": "system", "content": prompt_template}, {"role": "user", "content": format_user_prompt(question, candidates)}]

def format_user_prompt(question: str, candidates: list[Candidate]) -> str:
    blocks = ["User question:", question, "", "Candidate legal articles:"]
    for candidate in candidates:
        text = candidate.article_text.strip() if candidate.article_text.strip() else "[MISSING_ARTICLE_TEXT]"
        blocks.extend(["", f"[{candidate.candidate_id}]", f"article_ref: {candidate.ref.raw}", f"law_id: {candidate.ref.law_id}", f"law_title: {candidate.ref.law_title}", f"article_no: {candidate.ref.article_no}", "article_text:", text])
    return "\n".join(blocks)

def call_openai_compatible(base_url: str, model: str, messages: list[dict[str, str]], temperature: float, timeout: float, *, disable_thinking: bool = False) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    request_body: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
    if disable_thinking:
        request_body["chat_template_kwargs"] = {"enable_thinking": False}
    payload = json.dumps(request_body).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"LLM request failed: {exc}") from exc
    try:
        return str(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("LLM response missing choices[0].message.content") from exc

def order_candidate_refs(original_articles: list[str], fallback_articles: list[str], audit: dict[str, Any], max_candidates: int) -> list[ArticleRef]:
    original_refs = parse_article_refs(original_articles)
    original_by_raw = {ref.raw: ref for ref in original_refs}
    ordered_raw: list[str] = []
    for raw in fallback_articles:
        if raw in original_by_raw:
            ordered_raw.append(raw)
    for field in ("answer_mentioned_removed_articles", "legal_basis_removed_articles", "domain_primary_removed_articles"):
        for raw in parse_list_field(audit.get(field)):
            if raw in original_by_raw:
                ordered_raw.append(raw)
    ordered_raw.extend(ref.raw for ref in original_refs)
    result: list[ArticleRef] = []
    seen: set[str] = set()
    for raw in ordered_raw:
        if raw in seen or raw not in original_by_raw:
            continue
        seen.add(raw)
        result.append(original_by_raw[raw])
        if len(result) >= max_candidates:
            break
    return result

def parse_article_ref(value: str) -> ArticleRef | None:
    parts = [part.strip() for part in str(value or "").split("|", maxsplit=2)]
    if len(parts) != 3 or not all(parts):
        return None
    return ArticleRef(str(value).strip(), parts[0], parts[1], parts[2])

def parse_article_refs(values: Iterable[str]) -> list[ArticleRef]:
    return [ref for ref in (parse_article_ref(value) for value in values) if ref is not None]

def rebuild_docs_from_articles(articles: list[str]) -> list[str]:
    docs: list[str] = []
    seen: set[str] = set()
    for ref in parse_article_refs(articles):
        if ref.doc_ref not in seen:
            seen.add(ref.doc_ref)
            docs.append(ref.doc_ref)
    return docs

def build_article_text_lookup(rows: Iterable[dict[str, Any]]) -> ArticleTextLookup:
    exact: dict[str, str] = {}
    fallback: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for row in rows:
        law_id = str(row.get("law_id") or "").strip(); law_title = str(row.get("law_title") or "").strip(); article_no = str(row.get("article_no") or "").strip()
        if not law_id or not law_title or not article_no:
            continue
        key = f"{law_id}|{law_title}|{article_no}"
        text = str(row.get("article_text") or "")
        exact[key] = text
        fallback[(normalize_for_matching(law_id), normalize_for_matching(article_no))].append((key, text))
    return ArticleTextLookup(exact, dict(fallback))

def load_article_text_lookup(path: str | Path) -> ArticleTextLookup:
    try:
        import pandas as pd  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("pandas is required to read legal_articles.parquet") from exc
    frame = pd.read_parquet(path)
    return build_article_text_lookup(frame.to_dict(orient="records"))

def lookup_article_text(lookup: ArticleTextLookup, ref: ArticleRef) -> tuple[str, str | None, bool]:
    if ref.raw in lookup.exact:
        return lookup.exact[ref.raw], None, False
    matches = lookup.fallback.get((normalize_for_matching(ref.law_id), normalize_for_matching(ref.article_no)), [])
    if matches:
        warning = f"multiple fallback article_text matches for {ref.law_id}|{ref.article_no}; used first" if len(matches) > 1 else None
        return matches[0][1], warning, False
    return "[MISSING_ARTICLE_TEXT]", f"missing article_text for {ref.raw}", True

def detect_question_type(question: str) -> str:
    text = normalize_for_matching(question)
    if any(marker in text for marker in MULTI_PART_MARKERS) or re.search(r"\bvua\b.*\bvua\b", text):
        return "multi_part"
    if any(marker in text for marker in LIST_POLICY_MARKERS):
        return "list_policy"
    if any(marker in text for marker in SINGLE_FACT_MARKERS):
        return "single_fact"
    return "default"

def detect_domain(question: str, answer: str = "") -> str:
    text = normalize_for_matching(f"{question} {answer}")
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return domain
    return "other"

def has_local_indicator(question: str) -> bool:
    text = normalize_for_matching(question)
    return any(indicator in text for indicator in LOCAL_INDICATORS)

def question_explicitly_asks_old_law(question: str) -> bool:
    text = normalize_for_matching(question)
    return any(normalize_for_matching(old_law) in text for old_law, _ in CONFLICT_GROUPS) or "luat cu" in text or "quy dinh cu" in text

def fallback_or_top_original(record: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    patched = clone_submission_record(fallback)
    if patched.get("relevant_articles") and patched.get("relevant_docs"):
        return patched
    return fallback_from_original(record)

def fallback_from_original(record: dict[str, Any]) -> dict[str, Any]:
    patched = clone_submission_record(record)
    first = list(patched.get("relevant_articles") or [])[:1]
    patched["relevant_articles"] = first
    patched["relevant_docs"] = rebuild_docs_from_articles(first)
    ensure_non_empty_refs(patched, record)
    return patched

def clone_submission_record(record: dict[str, Any]) -> dict[str, Any]:
    return {"id": record["id"], "question": record["question"], "answer": record["answer"], "relevant_docs": list(record.get("relevant_docs") or []), "relevant_articles": list(record.get("relevant_articles") or [])}

def ensure_non_empty_refs(patched: dict[str, Any], original: dict[str, Any]) -> None:
    if patched.get("relevant_articles") and patched.get("relevant_docs"):
        return
    original_articles = list(original.get("relevant_articles") or [])
    if original_articles:
        patched["relevant_articles"] = original_articles[:1]
        patched["relevant_docs"] = rebuild_docs_from_articles(patched["relevant_articles"])
    if not patched.get("relevant_docs") and patched.get("relevant_articles"):
        patched["relevant_docs"] = rebuild_docs_from_articles(patched["relevant_articles"])

def should_process_record(record: dict[str, Any], audit: dict[str, Any], options: dict[str, Any], processed_count: int) -> bool:
    record_id = int(record["id"])
    if options.get("start_id") is not None and record_id < int(options["start_id"]):
        return False
    if options.get("end_id") is not None and record_id > int(options["end_id"]):
        return False
    if options.get("only_possible_overpruned") and not parse_bool(audit.get("possible_overpruned")):
        return False
    priority_domains = {item.strip() for item in str(options.get("priority_domains") or "").split(",") if item.strip()}
    domain = str(audit.get("domain") or detect_domain(record.get("question", ""), record.get("answer", "")))
    if priority_domains and domain not in priority_domains:
        return False
    if options.get("limit") is not None and processed_count >= int(options["limit"]):
        return False
    return True

def build_change(record: dict[str, Any], patched: dict[str, Any], *, mode: str, domain: str, question_type: str, possible_overpruned: bool, llm_success: bool, fallback_used: bool, warnings: list[str]) -> dict[str, Any]:
    return {"id": record["id"], "mode": mode, "domain": domain, "question_type": question_type, "possible_overpruned": possible_overpruned, "llm_success": llm_success, "fallback_used": fallback_used, "before_articles": list(record.get("relevant_articles") or []), "after_articles": list(patched.get("relevant_articles") or []), "selected_labels": [], "rejected_labels": [], "missing_article_text_refs": [], "warnings": warnings}

def build_report(input_records: list[dict[str, Any]], output_records: list[dict[str, Any]], changes: list[dict[str, Any]], counters: Counter[str], selected_label_counts: Counter[str], rejected_label_counts: Counter[str], processed_domains: Counter[str], fallback_domains: Counter[str], domain_stats: dict[str, Counter[str]], options: dict[str, Any]) -> dict[str, Any]:
    domain_summary: dict[str, dict[str, Any]] = {}
    for domain in sorted(set(processed_domains) | set(fallback_domains) | set(domain_stats)):
        stats = domain_stats.get(domain, Counter())
        processed = int(stats.get("processed", 0))
        domain_summary[domain] = {"processed": processed, "fallback": int(stats.get("fallback", 0)) + int(fallback_domains.get(domain, 0)), "avg_articles_after": round(float(stats.get("articles_after", 0)) / processed, 4) if processed else 0.0, "selected": int(stats.get("selected", 0)), "rejected": int(stats.get("rejected", 0))}
    return {
        "total_records": len(output_records), "mode": options["mode"], "max_candidates": int(options["max_candidates"]), "max_article_chars": int(options["max_article_chars"]),
        "records_changed": sum(change["before_articles"] != change["after_articles"] for change in changes),
        "llm_success_count": int(counters.get("llm_success_count", 0)), "llm_failure_count": int(counters.get("llm_failure_count", 0)), "json_parse_failure_count": int(counters.get("json_parse_failure_count", 0)),
        "fallback_count": sum(bool(change.get("fallback_used")) for change in changes), "empty_selection_fallback_count": int(counters.get("empty_selection_fallback_count", 0)), "invalid_candidate_id_count": int(counters.get("invalid_candidate_id_count", 0)),
        "avg_docs_before": average(len(record.get("relevant_docs") or []) for record in input_records), "avg_docs_after": average(len(record.get("relevant_docs") or []) for record in output_records),
        "avg_articles_before": average(len(record.get("relevant_articles") or []) for record in input_records), "avg_articles_after": average(len(record.get("relevant_articles") or []) for record in output_records),
        "selected_articles_count": int(counters.get("selected_articles_count", 0)), "rejected_articles_count": int(counters.get("rejected_articles_count", 0)), "missing_article_text_count": int(counters.get("missing_article_text_count", 0)),
        "processed_possible_overpruned_count": sum(bool(change.get("possible_overpruned")) and not change.get("fallback_used") for change in changes),
        "processed_domain_counts": dict(sorted(processed_domains.items())), "fallback_domain_counts": dict(sorted(fallback_domains.items())), "label_counts_selected": dict(sorted(selected_label_counts.items())), "label_counts_rejected": dict(sorted(rejected_label_counts.items())), "domain_summary": domain_summary,
    }

def load_submission(path: str | Path) -> list[dict[str, Any]]:
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_submission_records(loaded)
    return loaded

def validate_submission_records(records: Any) -> None:
    if not isinstance(records, list):
        raise ValueError("submission root must be a list")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"record {index} must be object")
        missing = REQUIRED_FIELDS.difference(record)
        if missing:
            raise ValueError(f"record {index} missing fields: {sorted(missing)}")

def load_audit_by_record(path: str | Path) -> dict[int, dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8", newline="") as file:
        return {int(row["id"]): row for row in csv.DictReader(file) if row.get("id")}

def parse_list_field(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            loaded = json.loads(text)
            if isinstance(loaded, list):
                return [str(item) for item in loaded if str(item)]
        except json.JSONDecodeError:
            pass
    return [part.strip() for part in text.split(" || ") if part.strip()]

def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}

def average(values: Iterable[int]) -> float:
    numbers = [float(value) for value in values]
    return round(sum(numbers) / len(numbers), 4) if numbers else 0.0

def normalize_for_matching(value: str) -> str:
    repaired = repair_common_mojibake(str(value or ""))
    repaired = strip_accents(repaired.replace("đ", "d").replace("Đ", "D"))
    return re.sub(r"\s+", " ", repaired.casefold()).strip()

def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")

def repair_common_mojibake(value: str) -> str:
    replacements = {"Ä": "Đ", "Ä‘": "đ", "Äu": "Điều", "Äiá»u": "Điều", "Ä‘iá»u": "điều", "NÄ-CP": "NĐ-CP", "QÄ-UBND": "QĐ-UBND", "NQ-HÄND": "NQ-HĐND", "HÄND": "HĐND", "nhá»¯ng": "những", "bao gá»“m": "bao gồm", "cÃ¡c trÆ°á»ng há»£p": "các trường hợp", "Ä‘iá»u kiá»‡n": "điều kiện", "há»“ sÆ¡": "hồ sơ", "thá»§ tá»¥c": "thủ tục", "quy trÃ¬nh": "quy trình", "chÃ­nh sÃ¡ch": "chính sách", "má»©c pháº¡t": "mức phạt", "Ä‘á»“ng thá»i": "đồng thời", "vÃ  náº¿u": "và nếu", "cÃ¹ng lÃºc": "cùng lúc"}
    repaired = value
    for old, new in replacements.items():
        repaired = repaired.replace(old, new)
    return repaired

def write_json(path: str | Path, value: Any) -> None:
    output_path = Path(path); output_path.parent.mkdir(parents=True, exist_ok=True); output_path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    output_path = Path(path); output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for row in rows:
            clean = {key: value for key, value in row.items() if not key.startswith("_")}
            file.write(json.dumps(clean, ensure_ascii=False) + "\n")

def write_flat_zip(path: str | Path, records: list[dict[str, Any]]) -> None:
    output_path = Path(path); output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("results.json", json.dumps(records, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    raise SystemExit(main())




