"""Exact retriever over canonical legal article indexes.

Exact retrieval chỉ trả về canonical article_id từ legal_articles/exact index.
Không sử dụng phapdien/anle và không sinh citation ngoài registry chính thức.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from backend.config.settings import get_settings
from backend.indexing.build_exact_index import load_exact_index
from backend.indexing.exact_index_store import ExactIndexStore

logger = logging.getLogger(__name__)

LAW_ID_PATTERN = re.compile(
    r"\b\d{1,3}/\d{4}/[A-ZĐ0-9]+(?:-[A-ZĐ0-9]+)*\b",
    re.IGNORECASE,
)
ARTICLE_NO_PATTERN = re.compile(
    r"(?:khoản\s+\d+\s+)?(?:điều|dieu)\s+0*(\d+[a-zA-Z]?)",
    re.IGNORECASE,
)
ACCOUNTING_ACCOUNT_PATTERN = re.compile(
    r"(?:tài\s*khoản|tai\s*khoan|tk)\s*(?:số|so)?\s*(\d{3,4})",
    re.IGNORECASE,
)
TITLE_CUES: tuple[str, ...] = (
    "luật hỗ trợ doanh nghiệp nhỏ và vừa",
    "luật hỗ trợ dnnvv",
    "luật doanh nghiệp",
    "luật kế toán",
)

LAW_ARTICLE_SCORE = 1.0
LAW_ID_SCORE = 0.75
ACCOUNTING_ACCOUNT_SCORE = 0.8
ARTICLE_NO_SCORE = 0.5


@dataclass(frozen=True)
class ExactHit:
    """Normalized exact retrieval hit."""

    article_id: str
    score: float
    match_type: str
    source: str = "exact"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExactQuerySignals:
    """Structured exact signals detected from one question."""

    law_ids: list[str]
    article_nos: list[str]
    accounting_accounts: list[str]
    title_cues: list[str]


class ExactLookupBackend(Protocol):
    """Lookup interface shared by DuckDB, JSON, and test fakes."""

    backend_name: str

    def find_by_law_article(self, law_id: str, article_no: str, *, limit: int) -> list[str]: ...

    def find_by_law_id(self, law_id: str, *, limit: int) -> list[str]: ...

    def find_by_article_no(self, article_no: str, *, limit: int) -> list[str]: ...

    def find_by_accounting_account(self, account: str, *, limit: int) -> list[str]: ...


class ExactRetriever:
    """Retrieve canonical legal article candidates from an exact index."""

    def __init__(
        self,
        index_path: str | Path | None = None,
        *,
        backend: ExactLookupBackend | None = None,
    ) -> None:
        if backend is not None:
            self.backend = backend
            self.index_path: Path | None = None
            return

        resolved_path = _resolve_default_index_path() if index_path is None else Path(index_path)
        if not resolved_path.exists():
            raise FileNotFoundError(f"Exact index file not found: {resolved_path}")

        self.index_path = resolved_path
        self.backend = _build_backend(resolved_path)

    def search(self, question: str, top_k: int = 5) -> list[ExactHit]:
        """Return canonical article candidates detected by exact signals."""

        normalized_question = _normalize_question(question)
        if not normalized_question or top_k <= 0:
            return []

        signals = detect_exact_query_signals(normalized_question)
        candidates: dict[str, ExactHit] = {}
        lookup_limit = max(top_k * 5, top_k)
        law_ids_with_strong_article_match: set[str] = set()

        for law_id in signals.law_ids:
            for article_no in signals.article_nos:
                article_ids = self.backend.find_by_law_article(law_id, article_no, limit=lookup_limit)
                if article_ids:
                    law_ids_with_strong_article_match.add(law_id)
                self._add_candidates(
                    candidates,
                    article_ids,
                    score=LAW_ARTICLE_SCORE,
                    match_type="law_id_article_no",
                    metadata={
                        "law_id": law_id,
                        "article_no": article_no,
                        "backend": self.backend.backend_name,
                        "title_cues": signals.title_cues,
                    },
                )

        for law_id in signals.law_ids:
            if law_id in law_ids_with_strong_article_match:
                # Khi đã có exact match theo cả mã văn bản + điều, không mở rộng ra
                # toàn bộ văn bản vì sẽ làm giảm precision của truy vấn rất rõ ràng.
                continue
            self._add_candidates(
                candidates,
                self.backend.find_by_law_id(law_id, limit=lookup_limit),
                score=LAW_ID_SCORE,
                match_type="law_id_only",
                metadata={
                    "law_id": law_id,
                    "backend": self.backend.backend_name,
                    "title_cues": signals.title_cues,
                },
            )

        for account in signals.accounting_accounts:
            self._add_candidates(
                candidates,
                self.backend.find_by_accounting_account(account, limit=lookup_limit),
                score=ACCOUNTING_ACCOUNT_SCORE,
                match_type="accounting_account",
                metadata={
                    "account": account,
                    "backend": self.backend.backend_name,
                    "title_cues": signals.title_cues,
                },
            )

        for article_no in signals.article_nos:
            self._add_candidates(
                candidates,
                self.backend.find_by_article_no(article_no, limit=lookup_limit),
                score=ARTICLE_NO_SCORE,
                match_type="article_no_only",
                metadata={
                    "article_no": article_no,
                    "backend": self.backend.backend_name,
                    "title_cues": signals.title_cues,
                },
            )

        return sorted(candidates.values(), key=lambda hit: hit.score, reverse=True)[:top_k]

    @staticmethod
    def _add_candidates(
        candidates: dict[str, ExactHit],
        article_ids: list[str],
        *,
        score: float,
        match_type: str,
        metadata: dict[str, Any],
    ) -> None:
        for article_id in article_ids:
            normalized_article_id = str(article_id or "").strip()
            if not normalized_article_id:
                logger.warning("Skip exact candidate with empty article_id: match_type=%s", match_type)
                continue

            candidate = ExactHit(
                article_id=normalized_article_id,
                score=score,
                match_type=match_type,
                metadata=dict(metadata),
            )
            existing = candidates.get(normalized_article_id)
            if existing is None or candidate.score > existing.score:
                candidates[normalized_article_id] = candidate


class _DuckDBExactBackend:
    backend_name = "duckdb"

    def __init__(self, path: Path) -> None:
        self.store = ExactIndexStore(path)

    def find_by_law_article(self, law_id: str, article_no: str, *, limit: int) -> list[str]:
        return self.store.find_by_law_article(law_id, article_no, limit=limit)

    def find_by_law_id(self, law_id: str, *, limit: int) -> list[str]:
        return self.store.find_by_law_id(law_id, limit=limit)

    def find_by_article_no(self, article_no: str, *, limit: int) -> list[str]:
        return self.store.find_by_article_no(article_no, limit=limit)

    def find_by_accounting_account(self, account: str, *, limit: int) -> list[str]:
        return self.store.find_by_accounting_account(account, limit=limit)


class _JsonExactBackend:
    backend_name = "json"

    def __init__(self, path: Path) -> None:
        self.index = load_exact_index(path)

    def find_by_law_article(self, law_id: str, article_no: str, *, limit: int) -> list[str]:
        values = self.index.get("by_law_article", {}).get(f"{law_id}|{article_no}", [])
        return _limit_ids(values, limit)

    def find_by_law_id(self, law_id: str, *, limit: int) -> list[str]:
        values = self.index.get("by_law_id", {}).get(law_id, [])
        return _limit_ids(values, limit)

    def find_by_article_no(self, article_no: str, *, limit: int) -> list[str]:
        values = self.index.get("by_article_no", {}).get(article_no, [])
        return _limit_ids(values, limit)

    def find_by_accounting_account(self, account: str, *, limit: int) -> list[str]:
        values = self.index.get("accounting_accounts", {}).get(account, [])
        return _limit_ids(values, limit)


def detect_exact_query_signals(question: str) -> ExactQuerySignals:
    """Detect deterministic exact lookup signals from a user question."""

    return ExactQuerySignals(
        law_ids=_unique_preserve_order(_normalize_law_id(match.group(0)) for match in LAW_ID_PATTERN.finditer(question)),
        article_nos=_unique_preserve_order(_normalize_article_no(match.group(1)) for match in ARTICLE_NO_PATTERN.finditer(question)),
        accounting_accounts=_unique_preserve_order(match.group(1) for match in ACCOUNTING_ACCOUNT_PATTERN.finditer(question)),
        title_cues=_detect_title_cues(question),
    )


def _resolve_default_index_path() -> Path:
    processed_dir = get_settings().paths.processed_dir
    duckdb_path = processed_dir / "exact_index.duckdb"
    if duckdb_path.exists():
        return duckdb_path

    json_path = processed_dir / "exact_index.json"
    if json_path.exists():
        return json_path

    return duckdb_path


def _build_backend(path: Path) -> ExactLookupBackend:
    suffix = path.suffix.lower()
    if suffix in {".duckdb", ".db"}:
        return _DuckDBExactBackend(path)
    if suffix == ".json":
        return _JsonExactBackend(path)
    raise ValueError(f"Unsupported exact index format: {path}")


def _normalize_question(question: str) -> str:
    if question is None:
        return ""
    return str(question).strip()


def _normalize_law_id(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip()).upper()


def _normalize_article_no(value: str) -> str:
    normalized = str(value or "").strip().lstrip("0")
    return f"Điều {normalized or '0'}"


def _detect_title_cues(question: str) -> list[str]:
    lowered = question.casefold()
    return [cue for cue in TITLE_CUES if cue in lowered]


def _unique_preserve_order(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _limit_ids(values: Any, limit: int) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value) for value in values[:limit] if str(value or "").strip()]
