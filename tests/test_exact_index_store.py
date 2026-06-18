from __future__ import annotations

import polars as pl

from backend.indexing.exact_index_store import ExactIndexStore, build_exact_duckdb_index


def test_build_exact_duckdb_index_and_lookup(tmp_path) -> None:
    source_path = tmp_path / "legal_articles.parquet"
    db_path = tmp_path / "exact_index.duckdb"
    pl.DataFrame(
        {
            "article_id": ["law-1|1", "law-1|2"],
            "law_id": ["law-1", "law-1"],
            "law_title": ["Luật thử nghiệm", "Luật thử nghiệm"],
            "article_no": ["Điều 1", "Điều 2"],
            "article_title": ["Quy định chung", "Xử phạt"],
            "content": [
                "Doanh nghiep phai nop bao cao trong 10 ngay vao tai khoan 642.",
                "Phat tien 5.000.000 dong doi voi hanh vi vi pham.",
            ],
            "source_url": ["https://example.test/1", "https://example.test/2"],
            "domain": ["legal", "legal"],
            "status": ["active", "active"],
        }
    ).write_parquet(source_path)

    result = build_exact_duckdb_index(source_path, db_path)

    assert result["article_count"] == 2
    assert db_path.exists()

    store = ExactIndexStore(db_path)
    assert store.get_metadata()["article_count"] == 2
    assert store.find_by_law_id("law-1") == ["law-1|1", "law-1|2"]
    assert store.find_by_law_article("law-1", "Điều 2") == ["law-1|2"]
    assert store.find_by_accounting_account("642") == ["law-1|1"]
    assert store.find_by_deadline("10 ngay") == ["law-1|1"]
    assert store.find_by_sanction_term("phat tien") == ["law-1|2"]

    article = store.get_article("law-1|1")
    assert article is not None
    assert article.article_id == "law-1|1"
    assert article.law_id == "law-1"


def test_exact_store_deduplicates_article_id_query(tmp_path) -> None:
    source_path = tmp_path / "legal_articles.parquet"
    db_path = tmp_path / "exact_index.duckdb"
    pl.DataFrame(
        {
            "article_id": ["a-1"],
            "law_id": ["law-1"],
            "law_title": ["Luật thử nghiệm"],
            "article_no": ["Điều 1"],
            "article_title": [""],
            "content": ["Noi dung."],
            "source_url": [""],
            "domain": [""],
            "status": [""],
        }
    ).write_parquet(source_path)
    build_exact_duckdb_index(source_path, db_path)

    store = ExactIndexStore(db_path)

    assert [item.article_id for item in store.get_articles_by_ids(["a-1", "a-1", ""])] == ["a-1"]
