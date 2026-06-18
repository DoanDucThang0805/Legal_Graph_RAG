from __future__ import annotations

from pathlib import Path

import pytest

from backend.retrieval.exact_retriever import (
    ExactRetriever,
    detect_exact_query_signals,
)


class FakeExactBackend:
    backend_name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], int]] = []
        self.by_law_article = {
            ("04/2017/QH14", "Điều 4"): ["article-law-4"],
        }
        self.by_law_id = {
            "04/2017/QH14": ["article-law-4", "article-law-other"],
        }
        self.by_article_no = {
            "Điều 4": ["article-law-4", "article-other-law-4"],
        }
        self.by_accounting_account = {
            "642": ["article-account-642"],
            "111": ["article-account-111"],
        }

    def find_by_law_article(self, law_id: str, article_no: str, *, limit: int) -> list[str]:
        self.calls.append(("law_article", (law_id, article_no), limit))
        return self.by_law_article.get((law_id, article_no), [])[:limit]

    def find_by_law_id(self, law_id: str, *, limit: int) -> list[str]:
        self.calls.append(("law_id", (law_id,), limit))
        return self.by_law_id.get(law_id, [])[:limit]

    def find_by_article_no(self, article_no: str, *, limit: int) -> list[str]:
        self.calls.append(("article_no", (article_no,), limit))
        return self.by_article_no.get(article_no, [])[:limit]

    def find_by_accounting_account(self, account: str, *, limit: int) -> list[str]:
        self.calls.append(("account", (account,), limit))
        return self.by_accounting_account.get(account, [])[:limit]


def test_empty_question_and_non_positive_top_k_return_empty_without_lookup() -> None:
    backend = FakeExactBackend()
    retriever = ExactRetriever(backend=backend)

    assert retriever.search("   ", top_k=5) == []
    assert retriever.search("Điều 4", top_k=0) == []
    assert backend.calls == []


def test_detect_article_no_variants() -> None:
    signals = detect_exact_query_signals("Theo khoản 1 Điều 04 thì xử lý thế nào?")

    assert signals.article_nos == ["Điều 4"]


def test_law_id_and_article_no_return_strongest_match_type() -> None:
    retriever = ExactRetriever(backend=FakeExactBackend())

    hits = retriever.search("Theo Điều 04 Luật 04/2017/QH14 thì sao?", top_k=5)

    assert hits[0].article_id == "article-law-4"
    assert hits[0].score == 1.0
    assert hits[0].match_type == "law_id_article_no"
    assert hits[0].source == "exact"
    assert hits[0].metadata["law_id"] == "04/2017/QH14"
    assert hits[0].metadata["article_no"] == "Điều 4"


def test_accounting_account_detection() -> None:
    retriever = ExactRetriever(backend=FakeExactBackend())

    hits = retriever.search("Chi phí này hạch toán vào TK 642 hay tài khoản 111?", top_k=5)

    assert {hit.article_id for hit in hits} == {"article-account-642", "article-account-111"}
    assert all(hit.match_type == "accounting_account" for hit in hits)
    assert all(hit.source == "exact" for hit in hits)


def test_dedup_keeps_highest_score_for_same_article_id() -> None:
    retriever = ExactRetriever(backend=FakeExactBackend())

    hits = retriever.search("04/2017/QH14 Điều 4", top_k=10)
    hit_by_id = {hit.article_id: hit for hit in hits}

    assert hit_by_id["article-law-4"].score == 1.0
    assert hit_by_id["article-law-4"].match_type == "law_id_article_no"


def test_no_phapdien_or_anle_citations_in_output() -> None:
    retriever = ExactRetriever(backend=FakeExactBackend())

    hits = retriever.search("04/2017/QH14 Điều 4", top_k=5)

    assert hits
    assert all(hit.source == "exact" for hit in hits)
    assert all("phapdien_id" not in hit.metadata for hit in hits)
    assert all("unit_id" not in hit.metadata for hit in hits)


def test_missing_index_path_raises_clear_error(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.duckdb"

    with pytest.raises(FileNotFoundError, match="Exact index file not found"):
        ExactRetriever(missing_path)
