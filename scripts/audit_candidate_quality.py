"""Audit candidate quality between full and pruned legal RAG submissions."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


CONFLICT_GROUPS: tuple[tuple[str, str], ...] = (
    ("78/2006/QH11", "38/2019/QH14"),
    ("43/2013/QH13", "22/2023/QH15"),
    ("39/2018/NĐ-CP", "80/2021/NĐ-CP"),
    ("95/2013/NĐ-CP", "12/2022/NĐ-CP"),
)

LOCAL_DOC_PATTERNS = ("nq-hdnd", "qd-ubnd", "ubnd", "hdnd")
LOCAL_INDICATORS = (
    "tinh",
    "thanh pho",
    "huyen",
    "xa",
    "dia ban",
    "ha noi",
    "tp. ho chi minh",
    "ho chi minh",
    "da nang",
    "hai phong",
    "can tho",
    "binh duong",
    "dong nai",
    "khanh hoa",
    "lang son",
    "thua thien hue",
    "vinh long",
    "hau giang",
    "dong thap",
    "binh dinh",
    "vinh phuc",
)
LIST_POLICY_MARKERS = (
    "nhung gi",
    "nhung noi dung gi",
    "nhung chinh sach nao",
    "bao gom",
    "cac truong hop",
    "dieu kien gi",
    "cac dieu kien",
    "cac chinh sach",
)

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "tax": ("thue", "khai thue", "nop thue", "tien cham nop", "le phi mon bai", "hoa don"),
    "labor_social_insurance": ("lao dong", "nguoi lao dong", "bao hiem xa hoi", "bhxh", "bao hiem that nghiep", "hop dong lao dong"),
    "sme_support": ("doanh nghiep nho va vua", "dnnvv", "ho tro doanh nghiep", "khoi nghiep sang tao", "quy phat trien doanh nghiep"),
    "bidding": ("dau thau", "nha thau", "goi thau", "ho so du thau", "lua chon nha thau"),
    "accounting": ("ke toan", "bao cao tai chinh", "so ke toan", "chung tu ke toan", "tai khoan ke toan"),
    "business_registration": ("dang ky doanh nghiep", "giay chung nhan dang ky", "ho kinh doanh", "ma so doanh nghiep", "thanh lap doanh nghiep"),
    "consumer_data_ip": ("du lieu ca nhan", "bao ve nguoi tieu dung", "quyen rieng tu", "so huu tri tue", "nhan hieu", "ban quyen"),
    "commerce_contract": ("hop dong", "thuong mai", "mua ban hang hoa", "dich vu", "xuc tien thuong mai", "dai ly thuong mai"),
}

DOMAIN_PRIMARY_SOURCES: dict[str, tuple[str, ...]] = {
    "tax": ("38/2019/qh14", "luat quan ly thue", "126/2020/nd-cp", "125/2020/nd-cp"),
    "labor_social_insurance": ("45/2019/qh14", "bo luat lao dong", "41/2024/qh15", "luat bao hiem xa hoi", "12/2022/nd-cp"),
    "sme_support": ("04/2017/qh14", "luat ho tro doanh nghiep nho va vua", "80/2021/nd-cp", "quy phat trien doanh nghiep"),
    "bidding": ("22/2023/qh15", "luat dau thau", "24/2024/nd-cp"),
    "accounting": ("88/2015/qh13", "luat ke toan", "200/2014/tt-btc", "133/2016/tt-btc"),
    "business_registration": ("01/2021/nd-cp", "luat doanh nghiep", "59/2020/qh14"),
    "consumer_data_ip": ("20/2023/nd-cp", "luat bao ve quyen loi nguoi tieu dung", "luat so huu tri tue"),
    "commerce_contract": ("36/2005/qh11", "luat thuong mai", "91/2015/qh13", "bo luat dan su"),
}

OUTPUT_FIELDS = (
    "id",
    "question",
    "original_docs_count",
    "original_articles_count",
    "pruned_docs_count",
    "pruned_articles_count",
    "removed_articles_count",
    "kept_articles_count",
    "answer_mentioned_original_count",
    "answer_mentioned_pruned_count",
    "answer_mentioned_removed_count",
    "legal_basis_original_count",
    "legal_basis_pruned_count",
    "legal_basis_removed_count",
    "domain",
    "has_local_docs_original",
    "has_local_docs_pruned",
    "has_old_new_conflict_original",
    "has_old_new_conflict_pruned",
    "possible_overpruned",
    "risk_score",
    "removed_articles",
    "kept_articles",
    "answer_mentioned_removed_articles",
    "legal_basis_removed_articles",
    "domain_primary_removed_articles",
)


@dataclass(frozen=True)
class ArticleRef:
    raw: str
    law_id: str
    law_title: str
    article_no: str

    @property
    def doc_ref(self) -> str:
        return f"{self.law_id}|{self.law_title}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit candidate quality between full and pruned submissions.")
    parser.add_argument("--original", required=True)
    parser.add_argument("--pruned", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    original_records = load_submission(args.original)
    pruned_records = load_submission(args.pruned)
    rows = audit_submissions(original_records, pruned_records)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "summary.json", build_summary(rows))
    write_csv(output_dir / "by_record.csv", rows, OUTPUT_FIELDS)
    top_rows = sorted(rows, key=lambda row: (-int(row["risk_score"]), int(row["id"])))[:100]
    write_csv(output_dir / "top_rescue_candidates.csv", top_rows, OUTPUT_FIELDS)
    write_csv(output_dir / "domain_summary.csv", build_domain_summary(rows), None)
    return 0


def load_submission(path: str | Path) -> list[dict[str, Any]]:
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise ValueError("submission root must be a list")
    return loaded


def audit_submissions(original_records: list[dict[str, Any]], pruned_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(original_records) != len(pruned_records):
        raise ValueError("original and pruned submissions must have the same record count")
    rows: list[dict[str, Any]] = []
    for index, (original, pruned) in enumerate(zip(original_records, pruned_records, strict=True)):
        if original.get("id") != pruned.get("id"):
            raise ValueError(f"record id mismatch at index {index}: {original.get('id')} != {pruned.get('id')}")
        rows.append(audit_record(original, pruned))
    return rows


def audit_record(original: dict[str, Any], pruned: dict[str, Any]) -> dict[str, Any]:
    question = str(original.get("question") or "")
    answer = str(original.get("answer") or "")
    original_docs = list(original.get("relevant_docs") or [])
    pruned_docs = list(pruned.get("relevant_docs") or [])
    original_articles = list(original.get("relevant_articles") or [])
    pruned_articles = list(pruned.get("relevant_articles") or [])

    kept_articles = [article for article in original_articles if article in set(pruned_articles)]
    removed_articles = [article for article in original_articles if article not in set(pruned_articles)]
    original_refs = parse_article_refs(original_articles)
    pruned_refs = parse_article_refs(pruned_articles)
    removed_refs = parse_article_refs(removed_articles)
    kept_refs = parse_article_refs(kept_articles)
    domain = detect_domain(question, answer)

    answer_original = [ref.raw for ref in original_refs if is_answer_mentioned_article(ref, answer)]
    answer_pruned = [ref.raw for ref in pruned_refs if is_answer_mentioned_article(ref, answer)]
    answer_removed = [ref.raw for ref in removed_refs if is_answer_mentioned_article(ref, answer)]
    legal_original = [ref.raw for ref in original_refs if is_legal_basis_article(ref, answer)]
    legal_pruned = [ref.raw for ref in pruned_refs if is_legal_basis_article(ref, answer)]
    legal_removed = [ref.raw for ref in removed_refs if is_legal_basis_article(ref, answer)]
    domain_primary_removed = [ref.raw for ref in removed_refs if is_domain_primary_article(ref, domain)]

    old_removed_new_retained = [ref for ref in removed_refs if is_old_law_removed_with_new_retained(ref, kept_refs, answer)]
    noisy_removed_count = sum(1 for ref in removed_refs if is_local_doc(ref.doc_ref, question))
    possible_overpruned = is_possible_overpruned(
        original_articles_count=len(original_articles),
        pruned_articles_count=len(pruned_articles),
        answer_mentioned_removed_count=len(answer_removed),
        legal_basis_removed_count=len(legal_removed),
        domain_primary_removed_count=len(domain_primary_removed),
    )
    score = compute_risk_score(
        answer_mentioned_removed_count=len(answer_removed),
        legal_basis_removed_count=len(legal_removed),
        domain_primary_removed_count=len(domain_primary_removed),
        is_list_policy=is_list_policy_question(question),
        original_articles_count=len(original_articles),
        local_noisy_removed_count=noisy_removed_count,
        old_law_removed_new_retained_count=len(old_removed_new_retained),
    )

    return {
        "id": original.get("id"),
        "question": question,
        "original_docs_count": len(original_docs),
        "original_articles_count": len(original_articles),
        "pruned_docs_count": len(pruned_docs),
        "pruned_articles_count": len(pruned_articles),
        "removed_articles_count": len(removed_articles),
        "kept_articles_count": len(kept_articles),
        "answer_mentioned_original_count": len(answer_original),
        "answer_mentioned_pruned_count": len(answer_pruned),
        "answer_mentioned_removed_count": len(answer_removed),
        "legal_basis_original_count": len(legal_original),
        "legal_basis_pruned_count": len(legal_pruned),
        "legal_basis_removed_count": len(legal_removed),
        "domain": domain,
        "has_local_docs_original": any(is_local_doc(doc, question) for doc in original_docs),
        "has_local_docs_pruned": any(is_local_doc(doc, question) for doc in pruned_docs),
        "has_old_new_conflict_original": has_old_new_conflict(original_refs),
        "has_old_new_conflict_pruned": has_old_new_conflict(pruned_refs),
        "possible_overpruned": possible_overpruned,
        "risk_score": score,
        "removed_articles": removed_articles,
        "kept_articles": kept_articles,
        "answer_mentioned_removed_articles": answer_removed,
        "legal_basis_removed_articles": legal_removed,
        "domain_primary_removed_articles": domain_primary_removed,
    }


def parse_article_ref(value: str) -> ArticleRef | None:
    parts = [part.strip() for part in str(value or "").split("|", maxsplit=2)]
    if len(parts) != 3 or not all(parts):
        return None
    return ArticleRef(raw=str(value).strip(), law_id=parts[0], law_title=parts[1], article_no=parts[2])


def parse_article_refs(values: Iterable[str]) -> list[ArticleRef]:
    return [ref for ref in (parse_article_ref(value) for value in values) if ref is not None]


def extract_legal_basis_section(answer: str) -> str:
    normalized = normalize_for_matching(answer)
    markers = ("can cu phap ly", "căn cứ pháp lý", "cÄƒn cá»© phÃ¡p lÃ½")
    marker_positions = [normalized.find(normalize_for_matching(marker)) for marker in markers]
    valid_positions = [position for position in marker_positions if position >= 0]
    if not valid_positions:
        return ""
    return normalized[min(valid_positions):]


def is_answer_mentioned_article(ref: ArticleRef, answer: str) -> bool:
    normalized_answer = normalize_for_matching(answer)
    return normalize_for_matching(ref.law_id) in normalized_answer or normalize_for_matching(ref.article_no) in normalized_answer


def is_legal_basis_article(ref: ArticleRef, answer: str) -> bool:
    section = extract_legal_basis_section(answer)
    if not section:
        return False
    return normalize_for_matching(ref.law_id) in section or normalize_for_matching(ref.article_no) in section


def detect_domain(question: str, answer: str = "") -> str:
    text = normalize_for_matching(f"{question} {answer}")
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return domain
    return "other"


def is_domain_primary_article(ref: ArticleRef, domain: str) -> bool:
    sources = DOMAIN_PRIMARY_SOURCES.get(domain, ())
    if not sources:
        return False
    ref_text = normalize_for_matching(f"{ref.law_id} {ref.law_title}")
    return any(source in ref_text for source in sources)


def is_local_doc(doc_ref: str, question: str = "") -> bool:
    question_text = normalize_for_matching(question)
    if any(indicator in question_text for indicator in LOCAL_INDICATORS):
        return False
    doc_text = normalize_for_matching(doc_ref)
    return any(pattern in doc_text for pattern in LOCAL_DOC_PATTERNS)


def has_old_new_conflict(refs: Iterable[ArticleRef]) -> bool:
    law_ids = {ref.law_id for ref in refs}
    return any(old_law in law_ids and new_law in law_ids for old_law, new_law in CONFLICT_GROUPS)


def is_old_law_removed_with_new_retained(removed_ref: ArticleRef, retained_refs: Iterable[ArticleRef], answer: str) -> bool:
    retained_laws = {ref.law_id for ref in retained_refs}
    answer_text = normalize_for_matching(answer)
    for old_law, new_law in CONFLICT_GROUPS:
        if removed_ref.law_id == old_law and new_law in retained_laws and normalize_for_matching(old_law) not in answer_text:
            return True
    return False


def is_possible_overpruned(
    *,
    original_articles_count: int,
    pruned_articles_count: int,
    answer_mentioned_removed_count: int,
    legal_basis_removed_count: int,
    domain_primary_removed_count: int,
) -> bool:
    return (
        original_articles_count >= 6
        and pruned_articles_count <= 3
        and (answer_mentioned_removed_count > 0 or legal_basis_removed_count > 0 or domain_primary_removed_count > 0)
    )


def compute_risk_score(
    *,
    answer_mentioned_removed_count: int,
    legal_basis_removed_count: int,
    domain_primary_removed_count: int,
    is_list_policy: bool,
    original_articles_count: int,
    local_noisy_removed_count: int,
    old_law_removed_new_retained_count: int,
) -> int:
    score = 0
    score += 5 * answer_mentioned_removed_count
    score += 4 * legal_basis_removed_count
    score += 3 * domain_primary_removed_count
    score += 2 if is_list_policy else 0
    score += 1 if original_articles_count >= 7 else 0
    score -= 3 * local_noisy_removed_count
    score -= 3 * old_law_removed_new_retained_count
    return score


def is_list_policy_question(question: str) -> bool:
    text = normalize_for_matching(question)
    return any(marker in text for marker in LIST_POLICY_MARKERS)


def normalize_for_matching(value: str) -> str:
    repaired = repair_common_mojibake(str(value or ""))
    repaired = strip_accents(repaired.replace("đ", "d").replace("Đ", "D"))
    return re.sub(r"\s+", " ", repaired.casefold()).strip()


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def repair_common_mojibake(value: str) -> str:
    replacements = {
        "Ä": "Đ",
        "Ä‘": "đ",
        "Äu": "Điều",
        "Äiá»u": "Điều",
        "Ä‘iá»u": "điều",
        "CÄƒn cá»© phÃ¡p lÃ½": "Căn cứ pháp lý",
        "NÄ-CP": "NĐ-CP",
        "QÄ-UBND": "QĐ-UBND",
        "NQ-HÄND": "NQ-HĐND",
        "HÄND": "HĐND",
    }
    repaired = value
    for old, new in replacements.items():
        repaired = repaired.replace(old, new)
    return repaired


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    domain_counts = Counter(str(row["domain"]) for row in rows)
    domain_possible = Counter(str(row["domain"]) for row in rows if row["possible_overpruned"])
    total = len(rows)
    return {
        "total_records": total,
        "avg_original_docs": average(row["original_docs_count"] for row in rows),
        "avg_original_articles": average(row["original_articles_count"] for row in rows),
        "avg_pruned_docs": average(row["pruned_docs_count"] for row in rows),
        "avg_pruned_articles": average(row["pruned_articles_count"] for row in rows),
        "total_removed_articles": sum(int(row["removed_articles_count"]) for row in rows),
        "records_with_answer_mentioned_removed": sum(int(row["answer_mentioned_removed_count"]) > 0 for row in rows),
        "records_with_legal_basis_removed": sum(int(row["legal_basis_removed_count"]) > 0 for row in rows),
        "records_possible_overpruned": sum(bool(row["possible_overpruned"]) for row in rows),
        "domain_counts": dict(sorted(domain_counts.items())),
        "domain_possible_overpruned_counts": dict(sorted(domain_possible.items())),
        "top_50_risky_ids": [row["id"] for row in sorted(rows, key=lambda row: (-int(row["risk_score"]), int(row["id"])))[:50]],
    }


def build_domain_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["domain"])].append(row)
    summary_rows: list[dict[str, Any]] = []
    for domain in sorted(grouped):
        group = grouped[domain]
        summary_rows.append(
            {
                "domain": domain,
                "records": len(group),
                "possible_overpruned": sum(bool(row["possible_overpruned"]) for row in group),
                "removed_articles": sum(int(row["removed_articles_count"]) for row in group),
                "answer_mentioned_removed": sum(int(row["answer_mentioned_removed_count"]) for row in group),
                "legal_basis_removed": sum(int(row["legal_basis_removed_count"]) for row in group),
                "domain_primary_removed": sum(len(row["domain_primary_removed_articles"]) for row in group),
                "avg_risk_score": average(row["risk_score"] for row in group),
            }
        )
    return summary_rows


def average(values: Iterable[Any]) -> float:
    numbers = [float(value) for value in values]
    if not numbers:
        return 0.0
    return round(sum(numbers) / len(numbers), 4)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: Sequence[str] | None) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    resolved_fields = list(fieldnames or rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=resolved_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: serialize_csv_value(row.get(field)) for field in resolved_fields})


def serialize_csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return " || ".join(str(item) for item in value)
    return value


if __name__ == "__main__":
    raise SystemExit(main())
