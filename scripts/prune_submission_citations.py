"""Precision-oriented deterministic citation pruning for submission JSON."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

CONFLICT_GROUPS: tuple[tuple[str, str], ...] = (
    ("78/2006/QH11", "38/2019/QH14"),
    ("43/2013/QH13", "22/2023/QH15"),
    ("39/2018/NÄ-CP", "80/2021/NÄ-CP"),
    ("95/2013/NÄ-CP", "12/2022/NÄ-CP"),
)

SINGLE_FACT_PHRASES = (
    "bao lÃ¢u",
    "máº¥y ngÃ y",
    "tá»· lá»‡",
    "má»©c pháº¡t",
    "thá»i háº¡n",
    "Ä‘iá»u kiá»‡n gÃ¬",
    "ai bá»‹ xá»­ pháº¡t",
)
LIST_POLICY_PHRASES = (
    "nhá»¯ng gÃ¬",
    "nhá»¯ng ná»™i dung gÃ¬",
    "nhá»¯ng chÃ­nh sÃ¡ch nÃ o",
    "bao gá»“m",
    "cÃ¡c trÆ°á»ng há»£p",
)
LOCAL_DOC_PATTERNS = ("NQ-HÄND", "QÄ-UBND", "NQ-HDND", "QD-UBND")
LOCAL_INDICATORS = (
    "tá»‰nh",
    "thÃ nh phá»‘",
    "huyá»‡n",
    "quáº­n",
    "xÃ£",
    "phÆ°á»ng",
    "Ä‘á»‹a phÆ°Æ¡ng",
    "ubnd",
    "hÄ‘nd",
)
REQUIRED_FIELDS = {"id", "question", "answer", "relevant_docs", "relevant_articles"}


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
class ScoredArticle:
    ref: ArticleRef
    index: int
    score: int
    reasons: list[str]


@dataclass(frozen=True)
class Caps:
    max_docs: int
    max_articles: int


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    items = load_submission(args.input)
    pruned, report, changes = prune_submission(items, variant=args.variant)
    write_json(args.output, pruned)
    write_json(args.report, report)
    write_jsonl(args.changes, changes)
    if args.zip_output:
        write_flat_zip(args.output, args.zip_output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prune relevant_docs/relevant_articles for higher citation precision.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--changes", required=True)
    parser.add_argument("--zip-output", default=None)
    parser.add_argument("--variant", choices=("a", "b", "c", "d", "e", "f", "g", "h", "i"), required=True)
    return parser


def prune_submission(items: list[dict[str, Any]], *, variant: str) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    validate_items(items)
    output: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    rollback_count = 0
    warnings_count = 0
    records_changed = 0
    articles_removed = 0
    docs_removed = 0
    docs_before_total = 0
    docs_after_total = 0
    articles_before_total = 0
    articles_after_total = 0
    docs_gt_5_before = 0
    docs_gt_5_after = 0
    articles_gt_5_before = 0
    articles_gt_5_after = 0

    for item in items:
        before_docs = list(item["relevant_docs"])
        before_articles = list(item["relevant_articles"])
        patched, change = prune_record(item, variant=variant)
        output.append(patched)
        changes.append(change)

        after_docs = patched["relevant_docs"]
        after_articles = patched["relevant_articles"]
        docs_before_total += len(before_docs)
        docs_after_total += len(after_docs)
        articles_before_total += len(before_articles)
        articles_after_total += len(after_articles)
        docs_gt_5_before += int(len(before_docs) > 5)
        docs_gt_5_after += int(len(after_docs) > 5)
        articles_gt_5_before += int(len(before_articles) > 5)
        articles_gt_5_after += int(len(after_articles) > 5)
        rollback_count += int(change["rolled_back"])
        warnings_count += len(change["warnings"])
        records_changed += int(change["changed"])
        articles_removed += max(0, len(before_articles) - len(after_articles))
        docs_removed += max(0, len(before_docs) - len(after_docs))

    total = len(items)
    report = {
        "total_records": total,
        "records_changed": records_changed,
        "articles_removed": articles_removed,
        "docs_removed": docs_removed,
        "rollback_count": rollback_count,
        "warnings_count": warnings_count,
        "avg_docs_before": docs_before_total / total if total else 0.0,
        "avg_docs_after": docs_after_total / total if total else 0.0,
        "avg_articles_before": articles_before_total / total if total else 0.0,
        "avg_articles_after": articles_after_total / total if total else 0.0,
        "docs_gt_5_before": docs_gt_5_before,
        "docs_gt_5_after": docs_gt_5_after,
        "articles_gt_5_before": articles_gt_5_before,
        "articles_gt_5_after": articles_gt_5_after,
        "variant": variant,
        "docs_caps": docs_caps_for_report(variant),
        "articles_caps": articles_caps_for_report(variant),
        "rescued_articles_count": sum(len(change.get("rescued_articles", [])) for change in changes),
        "rescued_records_count": sum(bool(change.get("rescued_articles")) for change in changes),
        "rescue_candidates_count": sum(change.get("rescue_candidates_count", 0) for change in changes),
        "rescue_skipped_local_count": sum(change.get("rescue_skipped_local_count", 0) for change in changes),
        "rescue_skipped_old_law_count": sum(change.get("rescue_skipped_old_law_count", 0) for change in changes),
    }
    validate_items(output)
    return output, report, changes


def prune_record(item: dict[str, Any], *, variant: str) -> tuple[dict[str, Any], dict[str, Any]]:
    before_docs = list(item["relevant_docs"])
    before_articles = list(item["relevant_articles"])
    warnings: list[str] = []
    deduped_articles = deduplicate_preserve_order(before_articles)
    parsed_articles = [ref for ref in (parse_article_ref(article) for article in deduped_articles) if ref is not None]
    if not parsed_articles:
        return dict(item), build_change(item, before_docs, before_articles, before_docs, before_articles, warnings + ["no parseable articles; rolled back"], True)

    question_type = determine_question_type(item["question"])
    scoring = score_articles(
        parsed_articles,
        question=item["question"],
        answer=item["answer"],
        variant=variant,
    )

    if variant in {"g", "h", "i"}:
        base_caps = caps_for_variant("a", question_type)
        base_selected = apply_docs_cap_to_entries(select_articles(scoring, caps=base_caps, variant="a", answer=item["answer"]), base_caps)
        selected, rescue_meta = apply_targeted_rescue(
            variant=variant,
            original_item=item,
            scored=scoring,
            base_selected=base_selected,
            question_type=question_type,
        )
        caps = caps_for_variant(variant, question_type)
    else:
        caps = caps_for_variant(variant, question_type)
        selected = select_articles(scoring, caps=caps, variant=variant, answer=item["answer"])
        rescue_meta = empty_rescue_meta()

    selected_articles = [entry.ref.raw for entry in selected]
    selected_docs = rebuild_docs_from_articles(selected_articles)
    if len(selected_docs) > caps.max_docs:
        allowed_docs = set(selected_docs[: caps.max_docs])
        selected_articles = [article for article in selected_articles if parse_article_ref(article).doc_ref in allowed_docs]
        selected_docs = rebuild_docs_from_articles(selected_articles)

    if not selected_docs or not selected_articles:
        warnings.append("pruning would empty refs; rolled back")
        return dict(item), build_change(
            item,
            before_docs,
            before_articles,
            before_docs,
            before_articles,
            warnings,
            True,
            variant=variant,
            rescue_meta=rescue_meta,
        )

    patched = dict(item)
    patched["relevant_articles"] = selected_articles
    patched["relevant_docs"] = selected_docs
    return patched, build_change(
        item,
        before_docs,
        before_articles,
        selected_docs,
        selected_articles,
        warnings,
        False,
        variant=variant,
        rescue_meta=rescue_meta,
    )

def empty_rescue_meta() -> dict[str, Any]:
    return {
        "rescued_articles": [],
        "rescue_candidates_count": 0,
        "rescue_skipped_local_count": 0,
        "rescue_skipped_old_law_count": 0,
    }


def apply_targeted_rescue(
    *,
    variant: str,
    original_item: dict[str, Any],
    scored: list[ScoredArticle],
    base_selected: list[ScoredArticle],
    question_type: str,
) -> tuple[list[ScoredArticle], dict[str, Any]]:
    caps = caps_for_variant(variant, question_type)
    selected_by_index = {entry.index: entry for entry in base_selected}
    retained_refs = [entry.ref for entry in base_selected]
    removed = [entry for entry in scored if entry.index not in selected_by_index]
    meta = empty_rescue_meta()
    meta["rescue_candidates_count"] = len(removed)

    rescue_pool: list[ScoredArticle] = []
    if variant == "g":
        rescue_pool = [
            entry for entry in removed
            if article_explicitly_mentioned(entry.ref, original_item["answer"])
            or is_article_in_legal_basis_section(entry.ref, original_item["answer"])
        ]
    elif variant == "h":
        if is_high_risk_for_recall(original_item, base_selected, scored, question_type):
            rescue_pool = [entry for entry in sorted(removed, key=lambda item: (-item.score, item.index)) if entry_score_for_rescue(entry) >= RESCUE_SCORE_THRESHOLD][:1]
    elif variant == "i":
        rescue_limit = 2 if question_type == "list_policy" else 1
        rescue_pool = [
            entry for entry in sorted(removed, key=lambda item: (-item.score, item.index))
            if is_domain_primary_law(entry.ref, original_item["question"], original_item["answer"])
        ][:rescue_limit]

    for entry in rescue_pool:
        if len(selected_by_index) >= caps.max_articles:
            break
        if is_local_document(entry.ref) and not has_local_indicator(original_item["question"]):
            meta["rescue_skipped_local_count"] += 1
            continue
        if old_law_blocked_by_retained(entry.ref, retained_refs, original_item["answer"]):
            meta["rescue_skipped_old_law_count"] += 1
            continue
        selected_by_index[entry.index] = entry
        retained_refs.append(entry.ref)
        meta["rescued_articles"].append(entry.ref.raw)

    return [entry for entry in scored if entry.index in selected_by_index], meta


RESCUE_SCORE_THRESHOLD = 80


def entry_score_for_rescue(entry: ScoredArticle) -> int:
    return entry.score


def get_legal_basis_section(answer: str) -> str:
    normalized = normalize_for_matching(answer)
    markers = ("can cu phap ly", "căn cứ pháp lý", "cÄƒn cá»© phÃ¡p lÃ½")
    for marker in markers:
        marker_norm = normalize_for_matching(marker)
        index = normalized.find(marker_norm)
        if index >= 0:
            return normalized[index:]
    return ""


def is_article_in_legal_basis_section(ref: ArticleRef, answer: str) -> bool:
    section = get_legal_basis_section(answer)
    if not section:
        return False
    return normalize_for_matching(ref.law_id) in section or normalize_for_matching(ref.article_no) in section


def same_law_as_retained(ref: ArticleRef, retained_articles: list[ArticleRef]) -> bool:
    return any(ref.law_id == retained.law_id for retained in retained_articles)


def is_high_risk_for_recall(
    original_item: dict[str, Any],
    base_selected: list[ScoredArticle],
    scored: list[ScoredArticle],
    question_type: str,
) -> bool:
    question = normalize_for_matching(original_item["question"])
    recall_phrases = ("nhung gi", "bao gom", "cac truong hop", "noi dung", "chinh sach", "dieu kien")
    return (
        len(scored) >= 7
        and len(base_selected) <= 3
        and (question_type == "list_policy" or any(phrase in question for phrase in recall_phrases))
    )


def old_law_blocked_by_retained(ref: ArticleRef, retained_articles: list[ArticleRef], answer: str) -> bool:
    retained_laws = {article.law_id for article in retained_articles}
    for old_law, new_law in CONFLICT_GROUPS:
        if ref.law_id == old_law and new_law in retained_laws and normalize_for_matching(old_law) not in normalize_for_matching(answer):
            return True
    return False


def is_domain_primary_law(ref: ArticleRef, question: str, answer: str) -> bool:
    text = normalize_for_matching(f"{question} {answer}")
    ref_text = normalize_for_matching(f"{ref.law_id} {ref.law_title}")
    domain_sources = {
        "tax": {
            "signals": ("thue", "khai thue", "nop thue", "tien cham nop", "le phi mon bai", "hoa don"),
            "sources": ("38/2019/qh14", "78/2006/qh11", "luat quan ly thue", "126/2020/nd-cp", "125/2020/nd-cp"),
        },
        "labor": {
            "signals": ("lao dong", "nguoi lao dong", "hop dong lao dong", "bao hiem xa hoi", "bhxh", "bao hiem that nghiep"),
            "sources": ("45/2019/qh14", "bo luat lao dong", "41/2024/qh15", "luat bao hiem xa hoi", "12/2022/nd-cp"),
        },
        "sme": {
            "signals": ("doanh nghiep nho va vua", "dnnvv", "ho tro doanh nghiep", "khoi nghiep sang tao", "cum lien ket nganh", "chuoi gia tri", "quy phat trien doanh nghiep nho va vua"),
            "sources": ("04/2017/qh14", "luat ho tro doanh nghiep nho va vua", "80/2021/nd-cp", "39/2019/nd-cp", "34/2018/nd-cp"),
        },
        "bidding": {
            "signals": ("dau thau", "nha thau", "goi thau", "ho so du thau", "lua chon nha thau"),
            "sources": ("22/2023/qh15", "luat dau thau", "24/2024/nd-cp"),
        },
        "accounting": {
            "signals": ("ke toan", "bao cao tai chinh", "tai khoan", "so ke toan", "chung tu ke toan"),
            "sources": ("200/2014/tt-btc", "133/2016/tt-btc", "luat ke toan"),
        },
    }
    for config in domain_sources.values():
        if any(signal in text for signal in config["signals"]):
            return any(source in ref_text for source in config["sources"])
    return False

def apply_docs_cap_to_entries(entries: list[ScoredArticle], caps: Caps) -> list[ScoredArticle]:
    selected_docs: list[str] = []
    selected: list[ScoredArticle] = []
    for entry in entries:
        doc_ref = entry.ref.doc_ref
        if doc_ref not in selected_docs:
            if len(selected_docs) >= caps.max_docs:
                continue
            selected_docs.append(doc_ref)
        selected.append(entry)
    return selected

def score_articles(refs: list[ArticleRef], *, question: str, answer: str, variant: str) -> list[ScoredArticle]:
    answer_folded = answer.casefold()
    question_folded = question.casefold()
    answer_normalized = normalize_for_matching(answer)
    question_normalized = normalize_for_matching(question)
    combined = f"{question} {answer}"
    laws_present = {ref.law_id for ref in refs}
    scored: list[ScoredArticle] = []
    for index, ref in enumerate(refs):
        score = 0
        reasons: list[str] = []
        law_in_answer = ref.law_id.casefold() in answer_folded or normalize_for_matching(ref.law_id) in answer_normalized
        article_in_answer = ref.article_no.casefold() in answer_folded or normalize_for_matching(ref.article_no) in answer_normalized
        if law_in_answer:
            score += 100
            reasons.append("law_id_in_answer")
        if article_in_answer:
            score += 80
            reasons.append("article_no_in_answer")
        if law_in_answer and article_in_answer:
            score += 60
            reasons.append("law_and_article_in_answer")
        if ref.law_id.casefold() in question_folded or normalize_for_matching(ref.law_id) in question_normalized:
            score += 30
            reasons.append("law_id_in_question")
        if title_keyword_overlap(ref.law_title, combined):
            score += 20
            reasons.append("title_keyword_overlap")
        if is_local_document(ref) and not has_local_indicator(question):
            score -= 40
            reasons.append("local_penalty")
        if old_law_penalty_applies(ref, laws_present, answer):
            score -= 50
            reasons.append("old_new_conflict_penalty")
        scored.append(ScoredArticle(ref=ref, index=index, score=score, reasons=reasons))
    return scored


def select_articles(scored: list[ScoredArticle], *, caps: Caps, variant: str, answer: str) -> list[ScoredArticle]:
    if variant == "c":
        preferred = [entry for entry in scored if article_explicitly_mentioned(entry.ref, answer)]
        ranked = sorted(preferred, key=lambda entry: (-entry.score, entry.index))
        if not ranked:
            ranked = sorted(scored, key=lambda entry: (-entry.score, entry.index))
        selected_indexes = {entry.index for entry in ranked[: caps.max_articles]}
    elif variant == "f":
        selected_indexes = select_variant_f_indexes(scored, caps=caps, answer=answer)
    else:
        ranked = sorted(scored, key=lambda entry: (-entry.score, entry.index))
        selected_indexes = {entry.index for entry in ranked[: caps.max_articles]}
    return [entry for entry in scored if entry.index in selected_indexes]


def select_variant_f_indexes(scored: list[ScoredArticle], *, caps: Caps, answer: str) -> set[int]:
    answer_mentioned = [entry for entry in scored if article_explicitly_mentioned(entry.ref, answer)]
    ranked_mentioned = sorted(answer_mentioned, key=lambda entry: (-mention_strength(entry.ref, answer), -entry.score, entry.index))
    selected: list[ScoredArticle] = ranked_mentioned[: caps.max_articles]
    selected_indexes = {entry.index for entry in selected}

    if len(selected) < caps.max_articles:
        backfill = [entry for entry in sorted(scored, key=lambda entry: (-entry.score, entry.index)) if entry.index not in selected_indexes]
        for entry in backfill:
            selected.append(entry)
            selected_indexes.add(entry.index)
            if len(selected) >= caps.max_articles:
                break
    return selected_indexes

def parse_article_ref(value: str) -> ArticleRef | None:
    parts = [part.strip() for part in str(value or "").split("|", maxsplit=2)]
    if len(parts) != 3 or not all(parts):
        return None
    return ArticleRef(raw=str(value).strip(), law_id=parts[0], law_title=parts[1], article_no=parts[2])


def deduplicate_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def rebuild_docs_from_articles(articles: list[str]) -> list[str]:
    docs: list[str] = []
    seen: set[str] = set()
    for article in articles:
        ref = parse_article_ref(article)
        if ref is None or ref.doc_ref in seen:
            continue
        seen.add(ref.doc_ref)
        docs.append(ref.doc_ref)
    return docs


def determine_question_type(question: str) -> str:
    text = normalize_for_matching(question)
    single_fact_markers = (
        *(normalize_for_matching(phrase) for phrase in SINGLE_FACT_PHRASES),
        "bao lau",
        "may ngay",
        "ty le",
        "muc phat",
        "thoi han",
        "dieu kien gi",
        "ai bi xu phat",
    )
    list_policy_markers = (
        *(normalize_for_matching(phrase) for phrase in LIST_POLICY_PHRASES),
        "nhung gi",
        "nhung noi dung gi",
        "nhung chinh sach nao",
        "bao gom",
        "cac truong hop",
    )
    if any(phrase in text for phrase in single_fact_markers):
        return "single_fact"
    if any(phrase in text for phrase in list_policy_markers):
        return "list_policy"
    return "default"

def caps_for_variant(variant: str, question_type: str) -> Caps:
    table = caps_table_for_variant(variant)
    return table[question_type]


def caps_table_for_variant(variant: str) -> dict[str, Caps]:
    if variant == "b":
        return {
            "single_fact": Caps(max_docs=1, max_articles=2),
            "list_policy": Caps(max_docs=3, max_articles=4),
            "default": Caps(max_docs=2, max_articles=3),
        }
    if variant in {"d", "f", "g", "h", "i"}:
        return {
            "single_fact": Caps(max_docs=2, max_articles=4),
            "list_policy": Caps(max_docs=4, max_articles=6),
            "default": Caps(max_docs=3, max_articles=5),
        }
    if variant == "e":
        return {
            "single_fact": Caps(max_docs=2, max_articles=5),
            "list_policy": Caps(max_docs=4, max_articles=7),
            "default": Caps(max_docs=3, max_articles=6),
        }
    return {
        "single_fact": Caps(max_docs=2, max_articles=3),
        "list_policy": Caps(max_docs=4, max_articles=5),
        "default": Caps(max_docs=3, max_articles=4),
    }


def docs_caps_for_report(variant: str) -> dict[str, int]:
    return {question_type: caps.max_docs for question_type, caps in caps_table_for_variant(variant).items()}


def articles_caps_for_report(variant: str) -> dict[str, int]:
    return {question_type: caps.max_articles for question_type, caps in caps_table_for_variant(variant).items()}

def is_local_document(ref: ArticleRef) -> bool:
    haystack = normalize_for_matching(f"{ref.law_id} {ref.law_title}")
    return any(normalize_for_matching(pattern) in haystack for pattern in LOCAL_DOC_PATTERNS)


def has_local_indicator(question: str) -> bool:
    text = normalize_for_matching(question)
    return any(normalize_for_matching(indicator) in text for indicator in LOCAL_INDICATORS)

def old_law_penalty_applies(ref: ArticleRef, laws_present: set[str], answer: str) -> bool:
    for old_law, new_law in CONFLICT_GROUPS:
        if ref.law_id == old_law and new_law in laws_present and old_law.casefold() not in answer.casefold():
            return True
    return False


def article_explicitly_mentioned(ref: ArticleRef, answer: str) -> bool:
    return mention_strength(ref, answer) > 0


def mention_strength(ref: ArticleRef, answer: str) -> int:
    folded = normalize_for_matching(answer)
    law_in_answer = normalize_for_matching(ref.law_id) in folded
    article_in_answer = normalize_for_matching(ref.article_no) in folded
    if law_in_answer and article_in_answer:
        return 3
    if law_in_answer:
        return 2
    if article_in_answer:
        return 1
    return 0


def normalize_for_matching(value: str) -> str:
    repaired = repair_common_mojibake(str(value or ""))
    repaired = strip_accents(repaired.replace("đ", "d").replace("Đ", "D"))
    return re.sub(r"\s+", " ", repaired.casefold()).strip()


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def repair_common_mojibake(value: str) -> str:
    replacements = {
        "Thá»i": "Thời",
        "thá»i": "thời",
        "háº¡n": "hạn",
        "bao lÃ¢u": "bao lâu",
        "tá»· lá»‡": "tỷ lệ",
        "má»©c pháº¡t": "mức phạt",
        "Ä‘iá»u kiá»‡n": "điều kiện",
        "xá»­ pháº¡t": "xử phạt",
        "nhá»¯ng": "những",
        "chÃ­nh sÃ¡ch": "chính sách",
        "bao gá»“m": "bao gồm",
        "cÃ¡c trÆ°á»ng há»£p": "các trường hợp",
        "QÄ-UBND": "QĐ-UBND",
        "QÄĐ-UBND": "QĐ-UBND",
        "Äiá»u": "Điều",
        "Äu": "Điều",
    }
    repaired = value
    for old, new in replacements.items():
        repaired = repaired.replace(old, new)
    return repaired

def title_keyword_overlap(title: str, text: str) -> bool:
    title_tokens = meaningful_tokens(title)
    text_tokens = set(meaningful_tokens(text))
    return any(token in text_tokens for token in title_tokens)


def meaningful_tokens(text: str) -> list[str]:
    stopwords = {
        "luat",
        "nghi",
        "dinh",
        "thong",
        "tu",
        "quyet",
        "hoi",
        "dong",
        "nhan",
        "dan",
        "ve",
        "cua",
        "va",
    }
    normalized = normalize_for_matching(text)
    tokens = re.findall(r"\w+", normalized)
    return [token for token in tokens if len(token) >= 4 and token not in stopwords and not token.isdigit()]

def build_change(
    item: dict[str, Any],
    before_docs: list[str],
    before_articles: list[str],
    after_docs: list[str],
    after_articles: list[str],
    warnings: list[str],
    rolled_back: bool,
    *,
    variant: str | None = None,
    rescue_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rescue_meta = rescue_meta or empty_rescue_meta()
    return {
        "id": item["id"],
        "variant": variant,
        "changed": before_docs != after_docs or before_articles != after_articles,
        "rolled_back": rolled_back,
        "before_docs": before_docs,
        "after_docs": after_docs,
        "before_articles": before_articles,
        "after_articles": after_articles,
        "rescued_articles": rescue_meta.get("rescued_articles", []),
        "removed_docs": [doc for doc in before_docs if doc not in after_docs],
        "removed_articles": [article for article in before_articles if article not in after_articles],
        "rescue_candidates_count": rescue_meta.get("rescue_candidates_count", 0),
        "rescue_skipped_local_count": rescue_meta.get("rescue_skipped_local_count", 0),
        "rescue_skipped_old_law_count": rescue_meta.get("rescue_skipped_old_law_count", 0),
        "warnings": warnings,
    }

def load_submission(path: str | Path) -> list[dict[str, Any]]:
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_items(loaded)
    return loaded


def validate_items(items: Any) -> None:
    if not isinstance(items, list):
        raise ValueError("submission root must be a list")
    seen_ids: set[int] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"item {index} must be an object")
        missing = REQUIRED_FIELDS.difference(item)
        if missing:
            raise ValueError(f"item {index} missing fields: {sorted(missing)}")
        if not isinstance(item["id"], int):
            raise ValueError(f"item {index} id must be int")
        if item["id"] in seen_ids:
            raise ValueError(f"duplicate id: {item['id']}")
        seen_ids.add(item["id"])
        if not isinstance(item["question"], str) or not isinstance(item["answer"], str):
            raise ValueError(f"item {index} question/answer must be strings")
        if not is_string_list(item["relevant_docs"]) or not is_string_list(item["relevant_articles"]):
            raise ValueError(f"item {index} refs must be non-empty string lists")


def is_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def write_json(path: str | Path, value: Any) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_flat_zip(results_path: str | Path, zip_path: str | Path) -> None:
    output_path = Path(zip_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.write(results_path, arcname="results.json")


if __name__ == "__main__":
    raise SystemExit(main())





















