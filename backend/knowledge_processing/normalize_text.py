"""Utilities for normalizing Vietnamese legal text."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE_PATTERN = re.compile(r"\s+")
_ARTICLE_PATTERN = re.compile(
    r"^\s*(?:điều|dieu)\s*0*([0-9]+[a-zA-Z]?)\s*[\.:：-]?\s*$",
    re.IGNORECASE,
)
_LAW_TYPE_MAP = {
    "bo_luat": "Bộ luật",
    "chi_thi": "Chỉ thị",
    "cong_van": "Công văn",
    "hien_phap": "Hiến pháp",
    "luat": "Luật",
    "nghi_dinh": "Nghị định",
    "nghi_quyet": "Nghị quyết",
    "phap_lenh": "Pháp lệnh",
    "quyet_dinh": "Quyết định",
    "sac_lenh": "Sắc lệnh",
    "thong_tu": "Thông tư",
    "thong_tu_lien_tich": "Thông tư liên tịch",
}


def normalize_vietnamese_text(text: str | None) -> str:
    """Normalize Unicode and whitespace without changing legal wording case."""

    if text is None:
        return ""

    normalized = unicodedata.normalize("NFC", str(text))
    normalized = normalized.replace("\u00a0", " ")
    normalized = normalized.replace("\ufeff", "")
    normalized = _WHITESPACE_PATTERN.sub(" ", normalized)
    return normalized.strip()


def normalize_article_no(article_no: str | None) -> str:
    """Normalize article number to the canonical ``Điều X`` format."""

    value = normalize_vietnamese_text(article_no)
    if not value:
        return ""

    match = _ARTICLE_PATTERN.match(value)
    if not match:
        return value.rstrip(".:")

    suffix = match.group(1)
    return f"Điều {suffix}"


def normalize_law_id(value: str | None) -> str:
    """Normalize legal document identifier while preserving official casing."""

    law_id = normalize_vietnamese_text(value)
    return law_id.rstrip(".,;:")


def normalize_law_type(law_type: str | None) -> str:
    """Normalize dataset law type labels to readable Vietnamese names."""

    value = normalize_vietnamese_text(law_type)
    if not value:
        return ""

    key = value.casefold().replace("-", "_").replace(" ", "_")
    key = re.sub(r"_+", "_", key).strip("_")
    mapped = _LAW_TYPE_MAP.get(key)
    if mapped:
        return mapped

    compare_key = _law_type_compare_key(value)
    for mapped_value in _LAW_TYPE_MAP.values():
        if compare_key == _law_type_compare_key(mapped_value):
            return mapped_value

    words = value.replace("_", " ").replace("-", " ").split()
    if not words:
        return ""
    return " ".join(word[:1].upper() + word[1:].lower() for word in words)


def normalize_law_title(
    law_type: str | None,
    law_id: str | None,
    title: str | None,
) -> str:
    """Build stable law title: ``Loại văn bản + mã văn bản + trích yếu``."""

    normalized_type = normalize_law_type(law_type)
    normalized_id = normalize_law_id(law_id)
    normalized_title = normalize_vietnamese_text(title)

    if normalized_title and normalized_id and normalized_id in normalized_title:
        rebuilt_title = _replace_law_type_prefix(normalized_title, normalized_type, normalized_id)
        if rebuilt_title:
            return rebuilt_title
        if not normalized_type or normalized_title.casefold().startswith(normalized_type.casefold()):
            return normalized_title

    parts = [normalized_type, normalized_id, normalized_title]

    # Dedupe theo thứ tự để tránh tiêu đề kiểu "Luật 04/... Luật 04/...".
    result_parts: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        key = part.casefold()
        if key in seen:
            continue
        seen.add(key)
        result_parts.append(part)

    return normalize_vietnamese_text(" ".join(result_parts))


def _replace_law_type_prefix(title: str, law_type: str, law_id: str) -> str:
    if not law_type or not law_id:
        return ""

    law_id_index = title.find(law_id)
    if law_id_index <= 0:
        return ""

    raw_prefix = title[:law_id_index].strip()
    if not raw_prefix:
        return ""

    comparable_prefix = re.sub(
        r"\b(so|số)\b\s*$",
        "",
        _law_type_compare_key(raw_prefix),
        flags=re.IGNORECASE,
    ).strip()
    if comparable_prefix != _law_type_compare_key(law_type):
        return ""

    suffix = title[law_id_index:]
    return normalize_vietnamese_text(f"{law_type} {suffix}")


def _law_type_compare_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    normalized = without_marks.replace("đ", "d").replace("-", " ").replace("_", " ")
    return re.sub(r"\s+", " ", normalized).strip()
