"""
Pháp Điển Việt Nam - Dataset Loader & Formatter
================================================

Tải bộ dữ liệu Bộ Pháp Điển Việt Nam (phapdien.moj.gov.vn) từ HuggingFace
và format thành bộ dữ liệu thống nhất phục vụ RAG indexing.

Dataset gốc: https://huggingface.co/datasets/tmquan/phapdien-moj-gov-vn

Cấu trúc dataset gốc gồm 6 subsets:
    - articles:           65,967 điều luật (bảng chính)
    - subjects:           202 đề mục
    - tree_nodes:         245 node phân cấp
    - ontology_topics:    42 chủ đề
    - ontology_subjects:  202 đề mục (ontology)
    - ontology_glossary:  116 thuật ngữ pháp lý

Output: Bộ dữ liệu phẳng (flat) gồm tất cả các Điều luật đã được
enrich metadata từ ontology, sẵn sàng cho embedding & indexing.

Usage:
    # Sử dụng mặc định
    loader = PhapdienDatasetLoader()
    unified_df = loader.run()

    # Custom config
    config = PhapdienConfig(
        output_dir="/path/to/output",
        output_formats=[OutputFormat.JSONL, OutputFormat.PARQUET],
        save_auxiliary=True,
    )
    loader = PhapdienDatasetLoader(config)
    unified_df = loader.run()
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from dataclasses import dataclass, field
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

    ARTICLES = "articles"
    SUBJECTS = "subjects"
    TREE_NODES = "tree_nodes"
    ONTOLOGY_TOPICS = "ontology_topics"
    ONTOLOGY_SUBJECTS = "ontology_subjects"
    ONTOLOGY_GLOSSARY = "ontology_glossary"


# Unified output column order — mỗi document RAG sẽ có đúng các cột này
UNIFIED_COLUMNS: list[str] = [
    "doc_id",
    "article_id",
    "article_title",
    "chapter_title",
    "topic_id",
    "topic_number",
    "topic_title_vi",
    "topic_title_en",
    "topic_note",
    "subject_id",
    "subject_number",
    "subject_title_vi",
    "subject_title_en",
    "content_text",
    "content_char_len",
    "content_word_count",
    "source_note_text",
    "related_note_text",
    "source_links_json",
    "source_url",
    "hierarchy_path",
    "scraped_at",
    "metadata_json",
]


@dataclass(frozen=True)
class PhapdienConfig:
    """Immutable configuration for the Pháp Điển pipeline.

    Attributes:
        dataset_name: HuggingFace dataset identifier.
        output_dir:   Directory to write processed files.
        output_formats: List of file formats to produce.
        save_auxiliary: Whether to save glossary, tree_nodes, etc.
    """

    dataset_name: str = "tmquan/phapdien-moj-gov-vn"
    output_dir: str = str(
        Path(__file__).resolve().parents[2] / "knowlegde_data" / "phapdien"
    )
    output_formats: tuple[OutputFormat, ...] = (
        OutputFormat.JSONL,
        OutputFormat.PARQUET,
    )
    save_auxiliary: bool = True


# ==========================================================================
# Ontology Enricher
# ==========================================================================


class PhapdienOntologyEnricher:
    """Build lookup tables từ ontology và enrich bảng articles.

    Chịu trách nhiệm:
      - Tạo dict tra cứu nhanh từ ``ontology_topics`` / ``ontology_subjects``.
      - Bổ sung tên tiếng Anh, ghi chú, tên chuẩn hoá vào articles.
    """

    def __init__(
        self,
        ontology_topics_df: pd.DataFrame,
        ontology_subjects_df: pd.DataFrame,
    ) -> None:
        self._topic_lookup = self._build_topic_lookup(ontology_topics_df)
        self._subject_lookup = self._build_subject_lookup(ontology_subjects_df)
        logger.info(
            "OntologyEnricher ready — %d topics, %d subjects",
            len(self._topic_lookup),
            len(self._subject_lookup),
        )

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def enrich(self, articles_df: pd.DataFrame) -> pd.DataFrame:
        """Enrich articles DataFrame tại chỗ và trả lại reference.

        Thêm các cột:
          - ``topic_title_en``, ``topic_note``
          - ``subject_title_en``
          - ``topic_title_vi_final``, ``subject_title_vi_final``
            (ưu tiên ontology, fallback articles)
        """
        df = articles_df

        # --- Topic enrichment ---
        df["topic_title_en"] = df["topic_id"].map(
            lambda tid: self._topic_lookup.get(tid, {}).get("title_en", ""),
        )
        df["topic_note"] = df["topic_id"].map(
            lambda tid: self._topic_lookup.get(tid, {}).get("note", ""),
        )

        # --- Subject enrichment ---
        df["subject_title_en"] = df["subject_id"].map(
            lambda sid: self._subject_lookup.get(sid, {}).get("title_en", ""),
        )

        # --- Tên VI chuẩn hoá (ontology ưu tiên, fallback articles) ---
        df["topic_title_vi_final"] = df.apply(
            lambda r: (
                self._topic_lookup.get(r["topic_id"], {}).get("title_vi", "")
                or str(r.get("topic_title_vi", ""))
            ),
            axis=1,
        )
        df["subject_title_vi_final"] = df.apply(
            lambda r: (
                self._subject_lookup.get(r["subject_id"], {}).get("title_vi", "")
                or str(r.get("subject_title_vi", ""))
            ),
            axis=1,
        )

        return df

    @property
    def topic_lookup(self) -> dict[str, dict[str, Any]]:
        return self._topic_lookup

    @property
    def subject_lookup(self) -> dict[str, dict[str, Any]]:
        return self._subject_lookup

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _build_topic_lookup(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
        """topic_id → {title_vi, title_en, note, article_count, demuc_count}"""
        lookup: dict[str, dict[str, Any]] = {}
        for _, row in df.iterrows():
            tid = row.get("topic_id", "")
            if not tid:
                continue
            lookup[str(tid)] = {
                "title_vi": row.get("topic_title_vi", ""),
                "title_en": row.get("topic_title_en", ""),
                "note": row.get("topic_note", ""),
                "article_count": int(row.get("article_count", 0)),
                "demuc_count": int(row.get("demuc_count", 0)),
            }
        return lookup

    @staticmethod
    def _build_subject_lookup(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
        """subject_id → {title_vi, title_en, article_count}"""
        lookup: dict[str, dict[str, Any]] = {}
        for _, row in df.iterrows():
            sid = row.get("subject_id", "")
            if not sid:
                continue
            lookup[str(sid)] = {
                "title_vi": row.get("subject_title_vi", ""),
                "title_en": row.get("subject_title_en", ""),
                "article_count": int(row.get("article_count", 0)),
            }
        return lookup


# ==========================================================================
# Data Formatter
# ==========================================================================


class PhapdienDataFormatter:
    """Chuyển đổi articles đã enrich thành schema thống nhất cho RAG.

    Chịu trách nhiệm:
      - Serialize ``source_links`` (nested list[dict]) → JSON string.
      - Xây dựng ``hierarchy_path`` phân cấp.
      - Đóng gói metadata phụ vào ``metadata_json``.
      - Chọn / đổi tên cột, fill NaN.
    """

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def format(self, enriched_df: pd.DataFrame) -> pd.DataFrame:
        """Trả về DataFrame mới với đúng schema ``UNIFIED_COLUMNS``."""
        df = enriched_df

        # --- Serialize source_links ---
        df["source_links_json"] = df["source_links"].apply(self._serialize_source_links)

        # --- Hierarchy path ---
        df["hierarchy_path"] = df.apply(
            lambda r: self._build_hierarchy_path(
                r.get("topic_title_vi_final", ""),
                r.get("subject_title_vi_final", ""),
                r.get("chapter_title", ""),
                r.get("article_title", ""),
            ),
            axis=1,
        )

        # --- Metadata JSON ---
        df["metadata_json"] = df.apply(self._build_metadata_json, axis=1)

        # --- Select & rename ---
        unified = pd.DataFrame(
            {
                "doc_id": df["record_id"],
                "article_id": df["article_id"],
                "article_title": df["article_title"],
                "chapter_title": df["chapter_title"],
                "topic_id": df["topic_id"],
                "topic_number": df["topic_number"],
                "topic_title_vi": df["topic_title_vi_final"],
                "topic_title_en": df["topic_title_en"],
                "topic_note": df["topic_note"],
                "subject_id": df["subject_id"],
                "subject_number": df["subject_number"],
                "subject_title_vi": df["subject_title_vi_final"],
                "subject_title_en": df["subject_title_en"],
                "content_text": df["content_text"],
                "content_char_len": df["content_char_len"],
                "content_word_count": df["content_word_count"],
                "source_note_text": df["source_note_text"],
                "related_note_text": df["related_note_text"],
                "source_links_json": df["source_links_json"],
                "source_url": df["source_url"],
                "hierarchy_path": df["hierarchy_path"],
                "scraped_at": df["scraped_at"],
                "metadata_json": df["metadata_json"],
            }
        )

        # --- Clean NaN ---
        str_cols = unified.select_dtypes(include=["object"]).columns
        unified[str_cols] = unified[str_cols].fillna("")

        int_cols = ["topic_number", "subject_number", "content_char_len", "content_word_count"]
        for col in int_cols:
            unified[col] = unified[col].fillna(0).astype(int)

        return unified

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_source_links(value: Any) -> str:
        """list[dict] | numpy.ndarray | None | NaN → JSON string.

        Note: HuggingFace ``.to_pandas()`` converts ``list`` columns to
        ``numpy.ndarray``, so we must handle both types.
        """
        if value is None or (isinstance(value, float)):
            return "[]"
        # numpy.ndarray → convert to list first
        items: list | None = None
        if isinstance(value, list):
            items = value
        elif hasattr(value, "tolist"):  # numpy.ndarray
            items = value.tolist()
        if items is not None:
            cleaned = [
                {"text": str(item.get("text", "")), "href": str(item.get("href", ""))}
                for item in items
                if isinstance(item, dict)
            ]
            return json.dumps(cleaned, ensure_ascii=False)
        return "[]"

    @staticmethod
    def _build_hierarchy_path(
        topic: str,
        subject: str,
        chapter: str,
        article: str,
    ) -> str:
        """Ghép 'Chủ đề > Đề mục > Chương > Điều', bỏ phần trống."""
        parts = [
            s.strip()
            for s in (str(topic), str(subject), str(chapter), str(article))
            if s and str(s).strip()
        ]
        return " > ".join(parts)

    @staticmethod
    def _build_metadata_json(row: pd.Series) -> str:
        """Đóng gói metadata phụ thành JSON string."""
        payload = {
            "article_anchor": row.get("article_anchor", ""),
            "topic_number": int(row.get("topic_number", 0)),
            "subject_number": int(row.get("subject_number", 0)),
            "topic_title_original": row.get("topic_title", ""),
            "subject_title_original": row.get("subject_title", ""),
            "topic_note": row.get("topic_note", ""),
        }
        return json.dumps(payload, ensure_ascii=False)


# ==========================================================================
# Dataset Writer
# ==========================================================================


class PhapdienDatasetWriter:
    """Ghi DataFrame ra file theo nhiều format.

    Hỗ trợ: JSONL, Parquet, CSV.
    """

    def __init__(self, output_dir: str) -> None:
        self._output_dir = output_dir
        os.makedirs(self._output_dir, exist_ok=True)

    def write(
        self,
        df: pd.DataFrame,
        filename: str,
        formats: tuple[OutputFormat, ...] | list[OutputFormat],
    ) -> list[str]:
        """Lưu *df* với *filename* (không extension) theo từng format.

        Returns:
            Danh sách absolute path của các file đã tạo.
        """
        saved: list[str] = []

        for fmt in formats:
            filepath = os.path.join(self._output_dir, f"{filename}.{fmt.value}")
            self._write_single(df, filepath, fmt)
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            logger.info("  ✓ Saved %s (%.1f MB)", filepath, size_mb)
            saved.append(filepath)

        return saved

    # ------------------------------------------------------------------

    @staticmethod
    def _write_single(df: pd.DataFrame, path: str, fmt: OutputFormat) -> None:
        """Dispatch ghi theo format."""
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
# Dataset Stats Reporter
# ==========================================================================


class PhapdienStatsReporter:
    """In thống kê tổng quan về bộ dữ liệu đã xử lý."""

    def report(self, df: pd.DataFrame) -> None:
        """In ra stdout."""
        sep = "=" * 70

        print(f"\n{sep}")
        print("📊 THỐNG KÊ BỘ DỮ LIỆU PHÁP ĐIỂN — UNIFIED FOR RAG")
        print(sep)

        print(f"\n📝 Tổng số điều luật : {len(df):,}")
        print(f"📋 Số trường thông tin: {len(df.columns)}")

        self._report_topics(df)
        self._report_subjects(df)
        self._report_content(df)
        self._report_missing(df)
        self._report_samples(df)

        print(f"\n{sep}")

    # ------------------------------------------------------------------

    @staticmethod
    def _report_topics(df: pd.DataFrame) -> None:
        stats = (
            df.groupby("topic_title_vi")
            .agg(count=("doc_id", "count"), avg_words=("content_word_count", "mean"))
            .sort_values("count", ascending=False)
        )
        print(f"\n🏛️  Số chủ đề (topics): {len(stats)}")
        print("  Top 10 chủ đề:")
        for i, (topic, row) in enumerate(stats.head(10).iterrows(), 1):
            print(f"    {i:2d}. {topic}: {row['count']:,} điều (avg {row['avg_words']:.0f} từ)")

    @staticmethod
    def _report_subjects(df: pd.DataFrame) -> None:
        count = df["subject_title_vi"].nunique()
        print(f"\n📂 Số đề mục (subjects): {count}")

    @staticmethod
    def _report_content(df: pd.DataFrame) -> None:
        wc = df["content_word_count"]
        print("\n📏 Nội dung điều luật:")
        print(f"    Tổng  : {wc.sum():>12,} từ")
        print(f"    TB    : {wc.mean():>12,.0f} từ/điều")
        print(f"    Min   : {wc.min():>12,} từ")
        print(f"    Max   : {wc.max():>12,} từ")
        print(f"    Median: {wc.median():>12,.0f} từ")

    @staticmethod
    def _report_missing(df: pd.DataFrame) -> None:
        check_cols = ["content_text", "article_title", "topic_title_vi", "subject_title_vi"]
        print("\n⚠️  Dữ liệu trống:")
        for col in check_cols:
            n_empty = (df[col] == "").sum()
            if n_empty:
                pct = n_empty / len(df) * 100
                print(f"    {col}: {n_empty:,} ({pct:.1f}%)")

    @staticmethod
    def _report_samples(df: pd.DataFrame, n: int = 2) -> None:
        print(f"\n📌 Mẫu dữ liệu ({n} bản ghi đầu tiên):")
        for idx, row in df.head(n).iterrows():
            print(f"\n  — Bản ghi {idx} —")
            print(f"    doc_id        : {row['doc_id']}")
            print(f"    article_id    : {row['article_id']}")
            print(f"    article_title : {str(row['article_title'])[:80]}")
            print(f"    hierarchy_path: {str(row['hierarchy_path'])[:100]}")
            print(f"    content_text  : {str(row['content_text'])[:150]}…")
            print(f"    source_url    : {row['source_url']}")


# ==========================================================================
# Main Loader (Orchestrator)
# ==========================================================================


class PhapdienDatasetLoader:
    """Orchestrator chính: tải → enrich → format → lưu.

    Usage::

        loader = PhapdienDatasetLoader()          # default config
        unified_df = loader.run()

        # hoặc custom:
        cfg = PhapdienConfig(output_dir="/tmp/out", save_auxiliary=False)
        loader = PhapdienDatasetLoader(cfg)
        unified_df = loader.run()
    """

    def __init__(self, config: Optional[PhapdienConfig] = None) -> None:
        self._config = config or PhapdienConfig()
        self._writer = PhapdienDatasetWriter(self._config.output_dir)
        self._formatter = PhapdienDataFormatter()
        self._reporter = PhapdienStatsReporter()

        # Populated after load
        self._raw_dataframes: dict[str, pd.DataFrame] = {}
        self._unified_df: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def config(self) -> PhapdienConfig:
        return self._config

    @property
    def raw_dataframes(self) -> dict[str, pd.DataFrame]:
        """Raw DataFrames keyed by subset name (available after ``load()``)."""
        return self._raw_dataframes

    @property
    def unified(self) -> Optional[pd.DataFrame]:
        """Unified DataFrame (available after ``run()`` or ``transform()``)."""
        return self._unified_df

    # ------------------------------------------------------------------
    # Pipeline steps (public, individually callable)
    # ------------------------------------------------------------------

    def load(self) -> dict[str, pd.DataFrame]:
        """Bước 1: Tải tất cả subsets từ HuggingFace.

        Returns:
            dict mapping SubsetName.value → DataFrame
        """
        logger.info("📥 Loading all subsets from %s …", self._config.dataset_name)

        for subset in SubsetName:
            name = subset.value
            logger.info("  Loading '%s' …", name)
            ds = load_dataset(self._config.dataset_name, name, split="train")
            df = ds.to_pandas()
            self._raw_dataframes[name] = df
            logger.info(
                "    ✓ %s: %s rows, %d cols %s",
                name,
                f"{len(df):,}",
                len(df.columns),
                list(df.columns),
            )

        return self._raw_dataframes

    def transform(self) -> pd.DataFrame:
        """Bước 2: Enrich + format → unified DataFrame.

        Requires ``load()`` to have been called first.

        Returns:
            Unified DataFrame ready for RAG indexing.
        """
        if not self._raw_dataframes:
            raise RuntimeError("No data loaded. Call load() first.")

        articles_df = self._raw_dataframes[SubsetName.ARTICLES.value].copy()
        logger.info("🔧 Transforming %s articles …", f"{len(articles_df):,}")

        # Enrich
        enricher = PhapdienOntologyEnricher(
            ontology_topics_df=self._raw_dataframes[SubsetName.ONTOLOGY_TOPICS.value],
            ontology_subjects_df=self._raw_dataframes[SubsetName.ONTOLOGY_SUBJECTS.value],
        )
        enriched_df = enricher.enrich(articles_df)

        # Format
        self._unified_df = self._formatter.format(enriched_df)
        logger.info(
            "  ✓ Unified: %s rows, %d columns",
            f"{len(self._unified_df):,}",
            len(self._unified_df.columns),
        )
        return self._unified_df

    def save(self) -> list[str]:
        """Bước 3: Lưu unified + auxiliary datasets.

        Requires ``transform()`` to have been called first.

        Returns:
            List of saved file paths.
        """
        if self._unified_df is None:
            raise RuntimeError("No unified data. Call transform() first.")

        fmts = self._config.output_formats
        all_saved: list[str] = []

        logger.info("💾 Saving datasets to %s …", self._config.output_dir)

        # Bộ chính
        all_saved.extend(self._writer.write(self._unified_df, "phapdien_unified", fmts))

        # Bộ phụ trợ
        if self._config.save_auxiliary:
            logger.info("📎 Saving auxiliary datasets …")
            auxiliary_sets = {
                "phapdien_glossary": SubsetName.ONTOLOGY_GLOSSARY.value,
                "phapdien_tree_nodes": SubsetName.TREE_NODES.value,
                "phapdien_ontology_topics": SubsetName.ONTOLOGY_TOPICS.value,
                "phapdien_subjects": SubsetName.SUBJECTS.value,
            }
            for filename, subset_key in auxiliary_sets.items():
                aux_df = self._raw_dataframes[subset_key].fillna("")
                all_saved.extend(self._writer.write(aux_df, filename, fmts))

        return all_saved

    def report(self) -> None:
        """Bước 4: In thống kê."""
        if self._unified_df is None:
            raise RuntimeError("No unified data. Call transform() first.")
        self._reporter.report(self._unified_df)

    # ------------------------------------------------------------------
    # Convenience: run toàn bộ pipeline
    # ------------------------------------------------------------------

    def run(self) -> pd.DataFrame:
        """Chạy pipeline end-to-end: load → transform → save → report.

        Returns:
            Unified DataFrame.
        """
        logger.info("=" * 60)
        logger.info("🚀 BẮT ĐẦU PIPELINE PHÁP ĐIỂN")
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

    loader = PhapdienDatasetLoader()
    unified_df = loader.run()

    # In 1 dòng dữ liệu đầu tiên để kiểm tra
    print("\n📌 Dòng đầu tiên:")
    first_row = unified_df.iloc[0]
    for col, val in first_row.items():
        print(f"  {col}: {str(val)[:200]}")
