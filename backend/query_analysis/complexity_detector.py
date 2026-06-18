"""Rule-based complexity detector for Vietnamese legal questions."""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Mapping

LOGGER = logging.getLogger(__name__)

SINGLE_HOP = "single_hop"
MULTI_HOP = "multi_hop"
MULTI_HOP_THRESHOLD = 1.0
DOMAIN_SIGNAL_THRESHOLD = 0.5

MULTI_HOP_CUES: tuple[str, ...] = (
    "vừa",
    "đồng thời",
    "sau đó",
    "trong khi",
    "ngoài ra",
    "bên cạnh đó",
    "cùng lúc",
    "mặt khác",
)


@dataclass(frozen=True)
class ComplexityDetection:
    """Question complexity signal for retrieval planning."""

    complexity: str
    score: float
    reasons: tuple[str, ...]
    matched_cues: tuple[str, ...]


def detect_complexity(
    question: str | None,
    domain_scores: Mapping[str, float] | None = None,
) -> ComplexityDetection:
    """Detect whether a legal question is single-hop or multi-hop.

    `domain_scores` is optional so this module remains independent in P3.T3.
    Later orchestration can pass scores from `classify_domain()` to increase
    multi-hop confidence when one question clearly touches multiple domains.
    """

    normalized_question = _normalize_query(question)
    if not normalized_question:
        LOGGER.warning("Cannot detect complexity for empty question; falling back to %s.", SINGLE_HOP)
        return ComplexityDetection(
            complexity=SINGLE_HOP,
            score=0.0,
            reasons=("empty_question",),
            matched_cues=(),
        )

    matched_cues = _find_multi_hop_cues(normalized_question)
    score = _score_cues(matched_cues)
    reasons: list[str] = [f"cue:{cue}" for cue in matched_cues]

    active_domain_count = _count_active_domains(domain_scores)
    if active_domain_count >= 2:
        # Nhiều domain là tín hiệu câu hỏi có thể cần nhiều bước suy luận,
        # nhưng không đủ mạnh bằng cue ngôn ngữ multi-hop rõ ràng.
        domain_score = min(active_domain_count * 0.35, 1.0)
        score += domain_score
        reasons.append(f"multiple_domain_signals:{active_domain_count}")

    rounded_score = round(score, 4)
    complexity = MULTI_HOP if rounded_score >= MULTI_HOP_THRESHOLD else SINGLE_HOP

    if not reasons:
        reasons.append("no_multi_hop_signal")

    return ComplexityDetection(
        complexity=complexity,
        score=rounded_score,
        reasons=tuple(reasons),
        matched_cues=tuple(matched_cues),
    )


def _find_multi_hop_cues(question: str) -> list[str]:
    matched_cues: list[str] = []
    for cue in MULTI_HOP_CUES:
        normalized_cue = _normalize_query(cue)
        if normalized_cue == "vừa":
            if _contains_vua_multi_hop_cue(question):
                matched_cues.append(cue)
            continue
        if _contains_cue(question, normalized_cue):
            matched_cues.append(cue)
    return matched_cues


def _score_cues(cues: list[str]) -> float:
    score = 0.0
    for cue in cues:
        score += 1.1 if " " in cue else 1.0
    if len(cues) >= 2:
        score += 0.3
    return score


def _count_active_domains(domain_scores: Mapping[str, float] | None) -> int:
    if not domain_scores:
        return 0
    return sum(1 for domain, score in domain_scores.items() if domain != "other" and score >= DOMAIN_SIGNAL_THRESHOLD)


def _normalize_query(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFC", value)
    normalized = normalized.replace("\u00a0", " ").casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def _contains_cue(question: str, cue: str) -> bool:
    if not cue:
        return False
    if " " in cue:
        return cue in question
    return re.search(rf"(?<!\w){re.escape(cue)}(?!\w)", question) is not None


def _contains_vua_multi_hop_cue(question: str) -> bool:
    vua_matches = re.findall(r"(?<!\w)vừa(?!\w)", question)
    if len(vua_matches) >= 2:
        return True

    # Tránh false positive rất phổ biến trong domain SME: "doanh nghiệp nhỏ và vừa".
    if "nhỏ và vừa" in question or "nho va vua" in question:
        return False

    return len(vua_matches) == 1
