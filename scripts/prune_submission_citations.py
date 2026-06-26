"""Precision-oriented deterministic citation pruning for submission JSON."""

from __future__ import annotations

import argparse
import json
import re
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
    parser.add_argument("--variant", choices=("a", "b", "c"), required=True)
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
    caps = caps_for_variant(variant, question_type)
    scored = score_articles(
        parsed_articles,
        question=item["question"],
        answer=item["answer"],
        variant=variant,
    )
    selected = select_articles(scored, caps=caps, variant=variant, answer=item["answer"])
    selected_articles = [entry.ref.raw for entry in selected]
    selected_docs = rebuild_docs_from_articles(selected_articles)
    if len(selected_docs) > caps.max_docs:
        allowed_docs = set(selected_docs[: caps.max_docs])
        selected_articles = [article for article in selected_articles if parse_article_ref(article).doc_ref in allowed_docs]
        selected_docs = rebuild_docs_from_articles(selected_articles)

    if not selected_docs or not selected_articles:
        warnings.append("pruning would empty refs; rolled back")
        return dict(item), build_change(item, before_docs, before_articles, before_docs, before_articles, warnings, True)

    patched = dict(item)
    patched["relevant_articles"] = selected_articles
    patched["relevant_docs"] = selected_docs
    return patched, build_change(item, before_docs, before_articles, selected_docs, selected_articles, warnings, False)


def score_articles(refs: list[ArticleRef], *, question: str, answer: str, variant: str) -> list[ScoredArticle]:
    answer_folded = answer.casefold()
    question_folded = question.casefold()
    combined = f"{question} {answer}"
    laws_present = {ref.law_id for ref in refs}
    scored: list[ScoredArticle] = []
    for index, ref in enumerate(refs):
        score = 0
        reasons: list[str] = []
        law_in_answer = ref.law_id.casefold() in answer_folded
        article_in_answer = ref.article_no.casefold() in answer_folded
        if law_in_answer:
            score += 100
            reasons.append("law_id_in_answer")
        if article_in_answer:
            score += 80
            reasons.append("article_no_in_answer")
        if law_in_answer and article_in_answer:
            score += 60
            reasons.append("law_and_article_in_answer")
        if ref.law_id.casefold() in question_folded:
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
    else:
        ranked = sorted(scored, key=lambda entry: (-entry.score, entry.index))
        selected_indexes = {entry.index for entry in ranked[: caps.max_articles]}
    return [entry for entry in scored if entry.index in selected_indexes]


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
    if any(normalize_for_matching(phrase) in text for phrase in SINGLE_FACT_PHRASES):
        return "single_fact"
    if any(normalize_for_matching(phrase) in text for phrase in LIST_POLICY_PHRASES):
        return "list_policy"
    return "default"

def caps_for_variant(variant: str, question_type: str) -> Caps:
    if variant == "b":
        table = {
            "single_fact": Caps(max_docs=1, max_articles=2),
            "list_policy": Caps(max_docs=3, max_articles=4),
            "default": Caps(max_docs=2, max_articles=3),
        }
        return table[question_type]
    table = {
        "single_fact": Caps(max_docs=2, max_articles=3),
        "list_policy": Caps(max_docs=4, max_articles=5),
        "default": Caps(max_docs=3, max_articles=4),
    }
    return table[question_type]


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
    folded = answer.casefold()
    return ref.law_id.casefold() in folded or ref.article_no.casefold() in folded


def normalize_for_matching(value: str) -> str:
    repaired = repair_common_mojibake(str(value or ""))
    repaired = repaired.replace("đ", "d").replace("Đ", "D")
    return re.sub(r"\s+", " ", repaired.casefold()).strip()


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
) -> dict[str, Any]:
    return {
        "id": item["id"],
        "changed": before_docs != after_docs or before_articles != after_articles,
        "rolled_back": rolled_back,
        "before_docs": before_docs,
        "after_docs": after_docs,
        "before_articles": before_articles,
        "after_articles": after_articles,
        "removed_docs": [doc for doc in before_docs if doc not in after_docs],
        "removed_articles": [article for article in before_articles if article not in after_articles],
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


