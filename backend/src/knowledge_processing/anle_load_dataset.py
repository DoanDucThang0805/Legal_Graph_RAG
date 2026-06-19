"""
Án Lệ Việt Nam - Dataset Loader & Formatter
=============================================

Tải bộ dữ liệu Án lệ Việt Nam (toaan.gov.vn) từ HuggingFace
và format thành bộ dữ liệu thống nhất phục vụ RAG indexing.

Dataset gốc: https://huggingface.co/datasets/tmquan/anle-toaan-gov-vn

Cấu trúc dataset gốc gồm 4 subsets:
    - documents:  1,963 án lệ (bảng chính, ~296MB)
    - sentences:  273,379 câu (tách sẵn theo câu)
    - embed:      1,963 embeddings (đã tính sẵn)
    - reduce:     1,963 toạ độ 2D (PCA/t-SNE/UMAP, dùng để visualize)

Output: Bộ dữ liệu phẳng (flat) gồm tất cả án lệ đã chuẩn hoá,
sẵn sàng cho embedding & indexing.

Usage:
    loader = AnleDatasetLoader()
    unified_df = loader.run()
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import pandas as pd
from datasets import load_dataset

logger = logging.getLogger(__name__)


# ==========================================================================
# Enums & Config
# ==========================================================================


class OutputFormat(str, Enum):
    """Supported output formats."""

    JSONL = "jsonl"
    PARQUET = "parquet"
    CSV = "csv"


class SubsetName(str, Enum):
    """Dataset subset (config) names on HuggingFace."""

    DOCUMENTS = "documents"
    SENTENCES = "sentences"
    EMBED = "embed"
    REDUCE = "reduce"


# Unified output column order
UNIFIED_COLUMNS: list[str] = [
    "doc_id",
    "doc_code",
    "precedent_number",
    "title",
    "subject",
    "case_type",
    "doc_type",
    "doc_subtype",
    "year",
    "issue_date",
    "adopted_date",
    "issuing_authority",
    "court_level",
    "jurisdiction",
    "applied_article_code",
    "applied_article_number",
    "applied_article_clause",
    "principle_text",
    "content_markdown",
    "content_char_len",
    "num_pages",
    "num_sections",
    "num_paragraphs",
    "num_sentences",
    "detail_url",
    "pdf_url",
    "source",
    "structure_json",
    "extracted_json",
    "parsed_at",
    "confidence",
    "metadata_json",
]


@dataclass(frozen=True)
class AnleConfig:
    """Immutable configuration for the Án Lệ pipeline.

    Attributes:
        dataset_name: HuggingFace dataset identifier.
        output_dir:   Directory to write processed files.
        output_formats: List of file formats to produce.
        save_auxiliary: Whether to save sentences subset separately.
    """

    dataset_name: str = "tmquan/anle-toaan-gov-vn"
    output_dir: str = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "knowlegde_data",
        "anle",
    )
    output_formats: tuple[OutputFormat, ...] = (
        OutputFormat.JSONL,
        OutputFormat.PARQUET,
    )
    save_auxiliary: bool = True


# ==========================================================================
# Data Formatter
# ==========================================================================


class AnleDataFormatter:
    """Chuyển đổi documents thành schema thống nhất cho RAG.

    Chịu trách nhiệm:
      - Chuẩn hoá và đổi tên cột.
      - Xử lý NaN/None.
      - Đóng gói metadata phụ vào ``metadata_json``.
    """

    def format(self, documents_df: pd.DataFrame) -> pd.DataFrame:
        """Trả về DataFrame mới với schema thống nhất."""
        df = documents_df.copy()
        logger.info("Formatting %s documents …", f"{len(df):,}")

        # --- Build metadata JSON ---
        df["metadata_json"] = df.apply(self._build_metadata_json, axis=1)

        # --- Select & rename ---
        unified = pd.DataFrame(
            {
                "doc_id": df["doc_name"],
                "doc_code": df["doc_code"],
                "precedent_number": df["precedent_number"],
                "title": df["title"],
                "subject": df["subject"],
                "case_type": df["case_type"],
                "doc_type": df["doc_type"],
                "doc_subtype": df["doc_subtype"],
                "year": df["year"],
                "issue_date": df["issue_date"],
                "adopted_date": df["adopted_date"],
                "issuing_authority": df["issuing_authority"],
                "court_level": df["court_level"],
                "jurisdiction": df["jurisdiction"],
                "applied_article_code": df["applied_article_code"],
                "applied_article_number": df["applied_article_number"],
                "applied_article_clause": df["applied_article_clause"],
                "principle_text": df["principle_text"],
                "content_markdown": df["markdown"],
                "content_char_len": df["char_len"],
                "num_pages": df["num_pages"],
                "num_sections": df["num_sections"],
                "num_paragraphs": df["num_paragraphs"],
                "num_sentences": df["num_sentences"],
                "detail_url": df["detail_url"],
                "pdf_url": df["pdf_url"],
                "source": df["source"],
                "structure_json": df["structure_json"],
                "extracted_json": df["extracted_json"],
                "parsed_at": df["parsed_at"],
                "confidence": df["confidence"],
                "metadata_json": df["metadata_json"],
            }
        )

        # --- Clean NaN ---
        str_cols = unified.select_dtypes(include=["object"]).columns
        unified[str_cols] = unified[str_cols].fillna("")

        int_cols = [
            "year", "num_pages", "num_sections", "num_paragraphs",
            "num_sentences", "content_char_len",
            "applied_article_number", "applied_article_clause",
        ]
        for col in int_cols:
            unified[col] = unified[col].fillna(0).astype(int)

        unified["confidence"] = unified["confidence"].fillna(0.0)

        logger.info(
            "  ✓ Unified: %s rows, %d columns",
            f"{len(unified):,}",
            len(unified.columns),
        )
        return unified

    @staticmethod
    def _build_metadata_json(row: pd.Series) -> str:
        """Đóng gói metadata phụ."""
        payload = {
            "text_hash": row.get("text_hash", ""),
            "parser_model": row.get("parser_model", ""),
        }
        return json.dumps(payload, ensure_ascii=False)


# ==========================================================================
# Dataset Writer
# ==========================================================================


class AnleDatasetWriter:
    """Ghi DataFrame ra file theo nhiều format."""

    def __init__(self, output_dir: str) -> None:
        self._output_dir = output_dir
        os.makedirs(self._output_dir, exist_ok=True)

    def write(
        self,
        df: pd.DataFrame,
        filename: str,
        formats: tuple[OutputFormat, ...] | list[OutputFormat],
    ) -> list[str]:
        """Lưu df ra file. Trả về list đường dẫn đã tạo."""
        saved: list[str] = []
        for fmt in formats:
            filepath = os.path.join(self._output_dir, f"{filename}.{fmt.value}")
            self._write_single(df, filepath, fmt)
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            logger.info("  ✓ Saved %s (%.1f MB)", filepath, size_mb)
            saved.append(filepath)
        return saved

    @staticmethod
    def _write_single(df: pd.DataFrame, path: str, fmt: OutputFormat) -> None:
        writers = {
            OutputFormat.JSONL: lambda: df.to_json(
                path, orient="records", lines=True, force_ascii=False,
            ),
            OutputFormat.PARQUET: lambda: df.to_parquet(
                path, index=False, engine="pyarrow",
            ),
            OutputFormat.CSV: lambda: df.to_csv(
                path, index=False, encoding="utf-8",
            ),
        }
        writer = writers.get(fmt)
        if writer is None:
            raise ValueError(f"Unsupported output format: {fmt!r}")
        writer()


# ==========================================================================
# Stats Reporter
# ==========================================================================


class AnleStatsReporter:
    """In thống kê tổng quan."""

    def report(self, df: pd.DataFrame) -> None:
        sep = "=" * 70

        print(f"\n{sep}")
        print("📊 THỐNG KÊ BỘ DỮ LIỆU ÁN LỆ — UNIFIED FOR RAG")
        print(sep)

        print(f"\n📝 Tổng số án lệ     : {len(df):,}")
        print(f"📋 Số trường thông tin: {len(df.columns)}")

        self._report_by_field(df, "case_type", "Loại vụ án")
        self._report_by_field(df, "court_level", "Cấp toà án")
        self._report_by_field(df, "doc_type", "Loại văn bản")
        self._report_year(df)
        self._report_content(df)
        self._report_principle(df)
        self._report_applied_articles(df)
        self._report_samples(df)

        print(f"\n{sep}")

    @staticmethod
    def _report_by_field(df: pd.DataFrame, field: str, label: str) -> None:
        counts = df[field].value_counts()
        print(f"\n🏛️  {label} ({len(counts)} loại):")
        for val, count in counts.head(10).items():
            print(f"    {val}: {count:,}")

    @staticmethod
    def _report_year(df: pd.DataFrame) -> None:
        years = df[df["year"] > 0]["year"]
        if len(years):
            print(f"\n📅 Năm: {int(years.min())} — {int(years.max())}")

    @staticmethod
    def _report_content(df: pd.DataFrame) -> None:
        cl = df["content_char_len"]
        print(f"\n📏 Nội dung:")
        print(f"    Tổng  : {cl.sum():>12,} ký tự")
        print(f"    TB    : {cl.mean():>12,.0f} ký tự/án lệ")
        print(f"    Min   : {cl.min():>12,}")
        print(f"    Max   : {cl.max():>12,}")
        print(f"    Median: {cl.median():>12,.0f}")

    @staticmethod
    def _report_principle(df: pd.DataFrame) -> None:
        has_principle = (df["principle_text"] != "").sum()
        print(f"\n⚖️  Án lệ có principle_text: {has_principle:,}/{len(df):,}")

    @staticmethod
    def _report_applied_articles(df: pd.DataFrame) -> None:
        has_article = (df["applied_article_code"] != "").sum()
        print(f"📎 Án lệ có applied_article: {has_article:,}/{len(df):,}")

    @staticmethod
    def _report_samples(df: pd.DataFrame, n: int = 2) -> None:
        print(f"\n📌 Mẫu dữ liệu ({n} bản ghi đầu tiên):")
        for idx, row in df.head(n).iterrows():
            print(f"\n  — Bản ghi {idx} —")
            print(f"    doc_id           : {row['doc_id']}")
            print(f"    precedent_number : {row['precedent_number']}")
            print(f"    title            : {str(row['title'])[:80]}")
            print(f"    case_type        : {row['case_type']}")
            print(f"    court_level      : {row['court_level']}")
            print(f"    year             : {row['year']}")
            print(f"    principle_text   : {str(row['principle_text'])[:120]}…")
            print(f"    content_markdown : {str(row['content_markdown'])[:120]}…")
            print(f"    detail_url       : {row['detail_url']}")


# ==========================================================================
# Main Loader (Orchestrator)
# ==========================================================================


class AnleDatasetLoader:
    """Orchestrator chính: tải → format → lưu.

    Usage::

        loader = AnleDatasetLoader()
        unified_df = loader.run()
    """

    def __init__(self, config: Optional[AnleConfig] = None) -> None:
        self._config = config or AnleConfig()
        self._writer = AnleDatasetWriter(self._config.output_dir)
        self._formatter = AnleDataFormatter()
        self._reporter = AnleStatsReporter()

        self._raw_dataframes: dict[str, pd.DataFrame] = {}
        self._unified_df: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def config(self) -> AnleConfig:
        return self._config

    @property
    def raw_dataframes(self) -> dict[str, pd.DataFrame]:
        return self._raw_dataframes

    @property
    def unified(self) -> Optional[pd.DataFrame]:
        return self._unified_df

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def load(self) -> dict[str, pd.DataFrame]:
        """Bước 1: Tải subsets từ HuggingFace.

        Chỉ tải ``documents`` và ``sentences`` (2 bảng hữu ích).
        Bỏ qua ``embed`` và ``reduce`` (đã pre-computed, ta sẽ tự tính).
        """
        logger.info("📥 Loading subsets from %s …", self._config.dataset_name)

        # Tải documents (bắt buộc)
        useful_subsets = [SubsetName.DOCUMENTS, SubsetName.SENTENCES]
        for subset in useful_subsets:
            name = subset.value
            logger.info("  Loading '%s' …", name)
            ds = load_dataset(self._config.dataset_name, name, split="train")
            df = ds.to_pandas()
            self._raw_dataframes[name] = df
            logger.info(
                "    ✓ %s: %s rows, %d cols",
                name,
                f"{len(df):,}",
                len(df.columns),
            )

        return self._raw_dataframes

    def transform(self) -> pd.DataFrame:
        """Bước 2: Format → unified DataFrame."""
        if not self._raw_dataframes:
            raise RuntimeError("No data loaded. Call load() first.")

        documents_df = self._raw_dataframes[SubsetName.DOCUMENTS.value]
        self._unified_df = self._formatter.format(documents_df)
        return self._unified_df

    def save(self) -> list[str]:
        """Bước 3: Lưu unified + auxiliary."""
        if self._unified_df is None:
            raise RuntimeError("No unified data. Call transform() first.")

        fmts = self._config.output_formats
        all_saved: list[str] = []

        logger.info("💾 Saving datasets to %s …", self._config.output_dir)

        # Bộ chính
        all_saved.extend(self._writer.write(self._unified_df, "anle_unified", fmts))

        # Bộ phụ trợ: sentences
        if self._config.save_auxiliary:
            logger.info("📎 Saving auxiliary datasets …")
            if SubsetName.SENTENCES.value in self._raw_dataframes:
                sentences_df = self._raw_dataframes[SubsetName.SENTENCES.value].copy()
                
                # Xử lý NaN cho cột string
                str_cols = sentences_df.select_dtypes(include=["object", "string"]).columns
                sentences_df[str_cols] = sentences_df[str_cols].fillna("")
                
                # Xử lý NaN cho cột số
                int_cols = ["year", "page", "index_in_paragraph", "global_index", "char_start", "char_end"]
                for col in int_cols:
                    if col in sentences_df.columns:
                        sentences_df[col] = pd.to_numeric(sentences_df[col], errors="coerce").fillna(0).astype(int)
                        
                all_saved.extend(self._writer.write(sentences_df, "anle_sentences", fmts))

        return all_saved

    def report(self) -> None:
        """Bước 4: In thống kê."""
        if self._unified_df is None:
            raise RuntimeError("No unified data. Call transform() first.")
        self._reporter.report(self._unified_df)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def run(self) -> pd.DataFrame:
        """Chạy pipeline end-to-end: load → transform → save → report."""
        logger.info("=" * 60)
        logger.info("🚀 BẮT ĐẦU PIPELINE ÁN LỆ")
        logger.info("=" * 60)

        self.load()
        self.transform()
        self.save()
        self.report()

        logger.info("✅ PIPELINE HOÀN TẤT — output: %s", self._config.output_dir)
        return self._unified_df  # type: ignore[return-value]


# ==========================================================================
# Entry point
# ==========================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    loader = AnleDatasetLoader()
    unified_df = loader.run()

    # In 1 dòng dữ liệu đầu tiên để kiểm tra
    print("\n📌 Dòng đầu tiên:")
    first_row = unified_df.iloc[0]
    for col, val in first_row.items():
        print(f"  {col}: {str(val)[:200]}")
