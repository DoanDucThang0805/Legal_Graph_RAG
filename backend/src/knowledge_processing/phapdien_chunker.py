"""
Pháp Điển - Structural-Aware Chunker
=====================================

Mục tiêu: Chia nhỏ các Điều luật (từ phapdien_unified) thành các chunks
phù hợp cho Embedding & Vector Search trong Graph RAG.

Chiến lược Hybrid 3 tầng:
1. Regex: Tự động phát hiện và tách theo "Khoản" (1., 2., 3. ...) với cờ MULTILINE.
2. Merge: Gộp các Khoản quá ngắn (< min_chunk_size) vào chunk liền kề.
3. Split: Nếu một Khoản quá dài (> max_chunk_size), dùng LangChain
   RecursiveCharacterTextSplitter để cắt nhỏ tiếp.

Context Enrichment:
- Mỗi chunk có `embed_text` = hierarchy_path + nội dung chunk.
- Khi Khoản dài bị split, mỗi sub-chunk vẫn giữ prefix Khoản gốc.

Input:  backend/knowlegde_data/phapdien/phapdien_unified.parquet
Output: backend/knowlegde_data/phapdien/phapdien_chunks.jsonl & .parquet
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex tìm ranh giới các Khoản: đứng đầu dòng, là số từ 1-99,
# theo sau là dấu chấm + khoảng trắng.
# Dùng re.MULTILINE để ^ match được với đầu mỗi dòng.
# Positive lookahead (?=.{15,}) đảm bảo nội dung đằng sau đủ dài.
# ---------------------------------------------------------------------------
KHOAN_PATTERN = re.compile(r"^([1-9]\d?)\.\s+(?=.{15,})", re.MULTILINE)

# Dấu câu/khoảng trắng thừa ở đầu chunk (thường do RecursiveCharacterTextSplitter
# cắt ngay sau separator ". " / "; " khiến sub-chunk bắt đầu bằng dấu câu mồ côi).
_LEADING_NOISE = re.compile(r"^[\s.;,:]+")


def _clean_lead(text: str) -> str:
    """Loại bỏ dấu câu/khoảng trắng thừa ở đầu chuỗi."""
    return _LEADING_NOISE.sub("", text).strip()


class PhapdienChunker:
    """Structural-aware chunker cho bộ Pháp Điển Việt Nam.

    Chiến lược:
      1. Tách Điều luật thành Khoản bằng Regex.
      2. Merge Khoản quá ngắn (< ``min_chunk_size``) vào chunk liền kề.
      3. Split Khoản quá dài (> ``max_chunk_size``) bằng LangChain splitter.
      4. Tạo ``embed_text`` = context prefix + chunk text để embedding.
    """

    def __init__(
        self,
        input_path: Optional[Union[str, Path]] = None,
        output_dir: Optional[Union[str, Path]] = None,
        max_chunk_size: int = 1000,
        min_chunk_size: int = 80,
        chunk_overlap: int = 150,
    ) -> None:
        base_dir = Path(__file__).resolve().parents[2] / "knowlegde_data" / "phapdien"

        if input_path:
            self.input_path = Path(input_path)
            if not self.input_path.exists():
                raise FileNotFoundError(f"Không tìm thấy file: {self.input_path}")
        else:
            self.input_path = base_dir / "phapdien_unified.parquet"
            if not self.input_path.exists():
                self.input_path = base_dir / "phapdien_unified.jsonl"
                if not self.input_path.exists():
                    raise FileNotFoundError(
                        f"Không tìm thấy file unified data tại {base_dir}"
                    )

        self.output_dir = Path(output_dir) if output_dir else base_dir
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.max_chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
        )

    # ------------------------------------------------------------------
    # Text splitting
    # ------------------------------------------------------------------

    def _split_by_khoan(self, text: str) -> list[str]:
        """Tách văn bản Điều luật thành các đoạn theo Khoản.

        - Intro (phần trước Khoản 1) luôn merge vào Khoản 1.
        - Trả về list[str], mỗi phần tử là 1 Khoản.
        """
        if not text:
            return []

        matches = list(KHOAN_PATTERN.finditer(text))
        if not matches:
            return [text]

        chunks: list[str] = []
        first_match_start = matches[0].start()
        intro = text[:first_match_start].strip() if first_match_start > 0 else ""

        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chunk_content = text[start:end].strip()

            # Merge intro vào Khoản 1
            if i == 0 and intro:
                chunk_content = f"{intro}\n{chunk_content}"

            if chunk_content:
                chunks.append(chunk_content)

        return chunks

    def _merge_short_chunks(self, chunks: list[str]) -> list[str]:
        """Gộp các Khoản quá ngắn (< min_chunk_size) vào chunk liền kề.

        Ưu tiên merge xuống (vào chunk tiếp theo). Nếu là chunk cuối
        thì merge lên (vào chunk trước đó).
        """
        if len(chunks) <= 1:
            return chunks

        merged: list[str] = []
        carry = ""

        for chunk in chunks:
            combined = f"{carry}\n{chunk}".strip() if carry else chunk

            if len(combined) < self.min_chunk_size:
                # Quá ngắn → carry để merge vào chunk tiếp theo
                carry = combined
            else:
                merged.append(combined)
                carry = ""

        # Nếu còn carry cuối cùng → merge vào chunk cuối
        if carry:
            if merged:
                merged[-1] = f"{merged[-1]}\n{carry}".strip()
            else:
                merged.append(carry)

        return merged

    def _split_long_chunk(self, chunk_text: str, khoan_header: str = "") -> list[str]:
        """Split Khoản quá dài bằng LangChain, giữ prefix Khoản.

        Args:
            chunk_text: Nội dung Khoản đầy đủ.
            khoan_header: Header Khoản (VD: "2. ") để nối vào sub-chunks.

        Returns:
            List các sub-chunk strings.
        """
        sub_chunks = self.text_splitter.split_text(chunk_text)

        # Làm sạch dấu câu mồ côi ở đầu + lọc bỏ mảnh vụn cực nhỏ (edge case
        # từ LangChain splitter)
        sub_chunks = [c for c in (_clean_lead(sc) for sc in sub_chunks) if len(c) >= 10]
        if not sub_chunks:
            return [chunk_text]  # fallback: giữ nguyên nếu lọc hết

        if not khoan_header or len(sub_chunks) <= 1:
            return sub_chunks

        # Thêm prefix Khoản vào các sub-chunk từ thứ 2 trở đi
        # để mỗi sub-chunk biết mình thuộc Khoản nào
        result = [sub_chunks[0]]
        for sc in sub_chunks[1:]:
            result.append(f"[...{khoan_header.strip()}] {sc}")
        return result

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_str(val: Any) -> str:
        """Safely convert value to string, handling NaN correctly."""
        if val is None:
            return ""
        try:
            if pd.isna(val):
                return ""
        except (TypeError, ValueError):
            pass
        return str(val).strip()

    def _extract_metadata(self, row: Any) -> dict[str, Any]:
        """Trích xuất metadata cần thiết từ Điều luật gốc sang cho Chunk."""
        return {
            "doc_id": self._safe_str(getattr(row, "doc_id", "")),
            "article_id": self._safe_str(getattr(row, "article_id", "")),
            "article_title": self._safe_str(getattr(row, "article_title", "")),
            "chapter_title": self._safe_str(getattr(row, "chapter_title", "")),
            "topic_id": self._safe_str(getattr(row, "topic_id", "")),
            "topic_title_vi": self._safe_str(getattr(row, "topic_title_vi", "")),
            "subject_id": self._safe_str(getattr(row, "subject_id", "")),
            "subject_title_vi": self._safe_str(
                getattr(row, "subject_title_vi", "")
            ),
            "hierarchy_path": self._safe_str(getattr(row, "hierarchy_path", "")),
            "source_url": self._safe_str(getattr(row, "source_url", "")),
        }

    @staticmethod
    def _build_context_prefix(metadata: dict[str, Any]) -> str:
        """Tạo context prefix cho embed_text theo đúng thứ tự phân cấp.

        Thứ tự: Chủ đề (topic) > Đề mục (subject) > Chương > Điều

        Dedup các cấp trùng liên tiếp (VD: topic == subject == "An ninh quốc gia")
        để tránh lặp "An ninh quốc gia > An ninh quốc gia > ..." gây phí token.
        """
        parts: list[str] = []
        for p in [
            metadata.get("topic_title_vi", ""),
            metadata.get("subject_title_vi", ""),
            metadata.get("chapter_title", ""),
            metadata.get("article_title", ""),
        ]:
            if p and (not parts or parts[-1] != p):
                parts.append(p)
        return " > ".join(parts) + "\n" if parts else ""

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_khoan_header(text: str) -> str:
        """Trích xuất header Khoản (VD: '2. ') từ đầu chunk text."""
        m = re.match(r"^(\d+\.\s+)", text)
        return m.group(1) if m else ""

    def process_row(self, row: Any) -> list[dict[str, Any]]:
        """Xử lý 1 Điều luật (row) thành N Chunks.

        Pipeline:
          1. Tách theo Khoản (Regex)
          2. Merge Khoản ngắn
          3. Split Khoản dài
          4. Gắn metadata + embed_text
        """
        text = self._safe_str(getattr(row, "content_text", ""))
        doc_id = self._safe_str(getattr(row, "doc_id", ""))
        article_id = self._safe_str(getattr(row, "article_id", ""))

        if not text or text == "nan":
            return []

        metadata = self._extract_metadata(row)
        context_prefix = self._build_context_prefix(metadata)

        # Bước 1: Tách theo Khoản
        khoan_chunks = self._split_by_khoan(text)

        # Bước 2: Merge Khoản ngắn
        khoan_chunks = self._merge_short_chunks(khoan_chunks)

        # Bước 3: Split Khoản dài + xây dựng final chunks
        final_chunks: list[dict[str, Any]] = []
        chunk_index = 0

        for k_chunk in khoan_chunks:
            if len(k_chunk) > self.max_chunk_size:
                # Trích header Khoản để giữ context cho sub-chunks
                khoan_header = self._extract_khoan_header(k_chunk)
                sub_chunks = self._split_long_chunk(k_chunk, khoan_header)
                for sc in sub_chunks:
                    final_chunks.append(
                        {
                            "chunk_id": f"{doc_id}::{article_id}::chunk::{chunk_index}",
                            "chunk_index": chunk_index,
                            "chunk_type": "split",
                            "chunk_text": sc,
                            "embed_text": f"{context_prefix}{sc}",
                            "chunk_char_len": len(sc),
                            "chunk_word_count": len(sc.split()),
                            **metadata,
                        }
                    )
                    chunk_index += 1
            else:
                c_type = "khoan" if len(khoan_chunks) > 1 else "full"
                final_chunks.append(
                    {
                        "chunk_id": f"{doc_id}::{article_id}::chunk::{chunk_index}",
                        "chunk_index": chunk_index,
                        "chunk_type": c_type,
                        "chunk_text": k_chunk,
                        "embed_text": f"{context_prefix}{k_chunk}",
                        "chunk_char_len": len(k_chunk),
                        "chunk_word_count": len(k_chunk.split()),
                        **metadata,
                    }
                )
                chunk_index += 1

        # Cập nhật tổng số chunk
        total_chunks = len(final_chunks)
        for c in final_chunks:
            c["chunk_total"] = total_chunks

        return final_chunks

    # ------------------------------------------------------------------
    # Pipeline runner
    # ------------------------------------------------------------------

    def run(self) -> pd.DataFrame:
        """Chạy pipeline chunking end-to-end.

        Returns:
            DataFrame chứa tất cả chunks.
        """
        logger.info("Loading data from: %s", self.input_path)
        if self.input_path.suffix == ".parquet":
            df = pd.read_parquet(self.input_path)
        else:
            df = pd.read_json(self.input_path, lines=True)

        logger.info("Total articles to process: %s", f"{len(df):,}")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        out_jsonl = self.output_dir / "phapdien_chunks.jsonl"
        out_parquet = self.output_dir / "phapdien_chunks.parquet"

        # Streaming ghi từng line ra JSONL để tối ưu Memory
        logger.info("Streaming chunks to %s ...", out_jsonl)
        total_chunks_created = 0
        failed_count = 0
        type_counts: dict[str, int] = {}
        chunk_sizes: list[int] = []

        with open(out_jsonl, "w", encoding="utf-8") as f:
            for row in tqdm(
                df.itertuples(index=False), total=len(df), desc="Chunking"
            ):
                try:
                    chunks = self.process_row(row)
                    for chunk in chunks:
                        f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                        total_chunks_created += 1
                        ct = chunk.get("chunk_type", "unknown")
                        type_counts[ct] = type_counts.get(ct, 0) + 1
                        chunk_sizes.append(chunk["chunk_char_len"])
                except Exception as e:
                    logger.error(
                        "Failed on doc_id=%s: %s",
                        getattr(row, "doc_id", "?"),
                        e,
                    )
                    failed_count += 1
                    continue

        if total_chunks_created == 0:
            logger.warning("⚠️ Không có chunk nào được tạo ra!")
            return pd.DataFrame()

        if failed_count > 0:
            logger.warning(
                "⚠️ %d/%d articles failed to chunk.", failed_count, len(df)
            )

        # Thống kê
        logger.info(
            "Generated %s chunks from %s articles.",
            f"{total_chunks_created:,}",
            f"{len(df):,}",
        )
        logger.info("Chunk types breakdown: %s", type_counts)

        if chunk_sizes:
            avg_size = sum(chunk_sizes) / len(chunk_sizes)
            min_size = min(chunk_sizes)
            max_size = max(chunk_sizes)
            sorted_sizes = sorted(chunk_sizes)
            median_size = sorted_sizes[len(sorted_sizes) // 2]
            logger.info(
                "Chunk size stats — avg: %d, median: %d, min: %d, max: %d chars",
                avg_size,
                median_size,
                min_size,
                max_size,
            )

        # Đọc lại từ JSONL và ghi Parquet theo chunks
        logger.info("Converting JSONL to Parquet (chunked)...")
        import pyarrow as pa
        import pyarrow.parquet as pq

        writer = None
        for chunk_batch in pd.read_json(out_jsonl, lines=True, chunksize=10_000):
            table = pa.Table.from_pandas(chunk_batch)
            if writer is None:
                writer = pq.ParquetWriter(str(out_parquet), table.schema)
            writer.write_table(table)

        if writer:
            writer.close()

        logger.info("Saving to %s ...", out_parquet)
        logger.info("✅ Chunking Pipeline Completed!")

        # Trả về DataFrame chunks cho pipeline tiếp theo
        result_df = pd.read_parquet(out_parquet)
        return result_df


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    chunker = PhapdienChunker()
    result = chunker.run()

    if result is not None and len(result) > 0:
        print(f"\n📌 Dòng đầu tiên:")
        first = result.iloc[0]
        for col, val in first.items():
            print(f"  {col}: {str(val)[:200]}")
