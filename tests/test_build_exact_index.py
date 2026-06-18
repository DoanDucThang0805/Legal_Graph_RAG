import json
from pathlib import Path

import polars as pl

from backend.indexing.build_exact_index import (
    build_exact_index,
    build_exact_index_from_dataframe,
    extract_accounting_accounts,
    extract_deadline_numbers,
    extract_sanction_terms,
)


def _sample_articles_df() -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "article_id": "L1|Luat Test|Dieu 1",
                "law_id": "L1",
                "law_title": "Luat Test",
                "article_no": "Dieu 01.",
                "article_title": "Quy dinh chung",
                "article_text": "Trong 10 ngay doanh nghiep phai nop bao cao.",
                "source_url": "https://example.test/1",
                "domain": "test",
                "status": "active",
            },
            {
                "article_id": "L1|Luat Test|Dieu 2",
                "law_id": "L1",
                "law_title": "Luat Test",
                "article_no": "Dieu 2",
                "article_title": "Xu phat",
                "article_text": "Phat tien 5.000.000 dong va hach toan tai khoan 642.",
                "source_url": "https://example.test/2",
                "domain": "test",
                "status": "active",
            },
        ]
    )


def test_build_exact_index_from_dataframe_uses_article_level_canonical_ids() -> None:
    index = build_exact_index_from_dataframe(_sample_articles_df())

    assert index["metadata"]["source"] == "legal_articles.parquet"
    assert "L1|Luat Test|Dieu 1" in index["articles"]
    assert index["by_law_id"]["L1"] == ["L1|Luat Test|Dieu 1", "L1|Luat Test|Dieu 2"]
    assert index["by_article_no"]["Điều 1"] == ["L1|Luat Test|Dieu 1"]
    assert index["by_law_article"]["L1|Điều 1"] == ["L1|Luat Test|Dieu 1"]


def test_extract_exact_features() -> None:
    text = "Phat tien 5.000.000 dong trong 10 ngay vao tai khoan 642."

    assert extract_accounting_accounts(text) == ["642"]
    assert extract_deadline_numbers(text) == ["10 ngay"]
    assert "phat tien" in extract_sanction_terms(text)
    assert "5.000.000 dong" in extract_sanction_terms(text)


def test_build_exact_index_writes_json_from_legal_articles_parquet(tmp_path: Path) -> None:
    input_path = tmp_path / "legal_articles.parquet"
    output_path = tmp_path / "exact_index.json"
    _sample_articles_df().write_parquet(input_path)

    index = build_exact_index(input_path, output_path)

    assert output_path.exists()
    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert loaded["metadata"]["source"] == "legal_articles.parquet"
    assert loaded["articles"] == index["articles"]
