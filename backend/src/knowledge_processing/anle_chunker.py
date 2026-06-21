"""
Án Lệ - Section-Aware Chunker
===============================

Mục tiêu: Chia nhỏ các Án Lệ (từ anle_unified + anle_sentences) thành chunks
phù hợp cho Embedding & Vector Search trong hệ thống RAG.

Chiến lược: Paragraph-level chunking sử dụng bảng sentences đã tách sẵn.
1. Gộp sentences cùng paragraph_id thành 1 đoạn văn.
2. Gộp liên tiếp các đoạn văn cùng section cho đến khi đạt max_chunk_size.
3. Context Enrichment: embed_text = metadata prefix + chunk text.

Bảng sentences đã cung cấp sẵn:
- section_kind: header | case_summary | findings | decision | footer
- paragraph_kind: text | list_item | numbered_decision | numbered_finding
- paragraph_id: nhóm câu cùng đoạn văn

Input:
  - anle_unified.parquet (1,963 án lệ)
  - anle_sentences.parquet (273,379 câu)

Output:
  - anle_chunks.jsonl & .parquet
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd
from tqdm import tqdm
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# Các section quan trọng cho RAG (bỏ qua header/footer vì ít giá trị ngữ nghĩa)
IMPORTANT_SECTIONS = {"case_summary", "findings", "decision"}

# Dấu câu/khoảng trắng thừa ở đầu đoạn (do tách câu lệch dấu chấm hoặc do
# RecursiveCharacterTextSplitter cắt ngay sau separator ". "). Không mang ngữ
# nghĩa nên strip để embed_text sạch hơn. Lưu ý KHÔNG strip "[" để giữ marker
# đánh số đoạn dạng "[1]", "[2]" trong phần Nhận định.
_LEADING_NOISE = re.compile(r"^[\s.;,:]+")


def _clean_lead(text: str) -> str:
    """Loại bỏ dấu câu/khoảng trắng thừa ở đầu chuỗi."""
    return _LEADING_NOISE.sub("", text).strip()


class AnleChunker:
    """Section-aware chunker cho bộ Án Lệ Việt Nam.

    Chiến lược:
      1. Gộp sentences cùng paragraph_id thành đoạn văn.
      2. Gộp liên tiếp các đoạn cùng section cho đến khi đạt max_chunk_size.
      3. Tạo embed_text = context prefix + chunk text.
    """

    def __init__(
        self,
        unified_path: Optional[Union[str, Path]] = None,
        sentences_path: Optional[Union[str, Path]] = None,
        output_dir: Optional[Union[str, Path]] = None,
        max_chunk_size: int = 1000,
        min_chunk_size: int = 80,
        chunk_overlap: int = 150,
        include_header_footer: bool = False,
    ) -> None:
        base_dir = Path(__file__).resolve().parents[2] / "knowlegde_data" / "anle"

        self.unified_path = Path(unified_path) if unified_path else base_dir / "anle_unified.parquet"
        self.sentences_path = Path(sentences_path) if sentences_path else base_dir / "anle_sentences.parquet"
        self.output_dir = Path(output_dir) if output_dir else base_dir

        for p in [self.unified_path, self.sentences_path]:
            if not p.exists():
                raise FileNotFoundError(f"Không tìm thấy file: {p}")

        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.include_header_footer = include_header_footer

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.max_chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
        )

    # ------------------------------------------------------------------
    # Paragraph assembly
    # ------------------------------------------------------------------

    @staticmethod
    def _assemble_paragraphs(doc_sentences: pd.DataFrame) -> list[dict[str, Any]]:
        """Gộp sentences cùng paragraph_id thành đoạn văn.

        Returns:
            List of dicts: {text, section_kind, paragraph_kind, paragraph_id}
        """
        paragraphs: list[dict[str, Any]] = []

        for (para_id, sec_kind), group in doc_sentences.groupby(
            ["paragraph_id", "section_kind"], sort=False
        ):
            # Sắp xếp theo index_in_paragraph để giữ đúng thứ tự
            group_sorted = group.sort_values("index_in_paragraph")
            text = " ".join(group_sorted["text"].astype(str).tolist())
            # Strip dấu câu thừa ở đầu đoạn (mỗi đoạn sẽ thành 1 dòng trong chunk
            # nên xử lý ở đây giúp sạch cả đầu chunk lẫn đầu các dòng nội bộ).
            text = _clean_lead(text)

            if text:
                paragraphs.append(
                    {
                        "text": text,
                        "section_kind": str(sec_kind),
                        "paragraph_kind": str(
                            group_sorted["paragraph_kind"].iloc[0]
                        ),
                        "paragraph_id": str(para_id),
                    }
                )

        return paragraphs

    # ------------------------------------------------------------------
    # Chunk assembly
    # ------------------------------------------------------------------

    def _group_paragraphs_into_chunks(
        self, paragraphs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Gộp liên tiếp các đoạn văn cùng section thành chunks.

        Logic:
          - Duyệt tuần tự các đoạn văn.
          - Nếu đoạn tiếp theo cùng section_kind VÀ tổng chars < max_chunk_size
            → gộp vào chunk hiện tại.
          - Nếu khác section hoặc vượt max_chunk_size → tạo chunk mới.
          - Chunk quá ngắn (< min_chunk_size) → gộp vào chunk trước.
        """
        if not paragraphs:
            return []

        raw_chunks: list[dict[str, Any]] = []
        current_texts: list[str] = []
        current_section = paragraphs[0]["section_kind"]
        current_len = 0

        for para in paragraphs:
            para_text = para["text"]
            para_section = para["section_kind"]

            # Bỏ qua header/footer nếu cấu hình không bao gồm
            if not self.include_header_footer and para_section not in IMPORTANT_SECTIONS:
                continue

            same_section = para_section == current_section
            would_fit = current_len + len(para_text) + 1 <= self.max_chunk_size

            if same_section and would_fit:
                current_texts.append(para_text)
                current_len += len(para_text) + 1
            else:
                # Flush chunk hiện tại
                if current_texts:
                    raw_chunks.append(
                        {
                            "text": "\n".join(current_texts),
                            "section_kind": current_section,
                        }
                    )
                # Bắt đầu chunk mới
                current_texts = [para_text]
                current_section = para_section
                current_len = len(para_text)

        # Flush chunk cuối
        if current_texts:
            raw_chunks.append(
                {
                    "text": "\n".join(current_texts),
                    "section_kind": current_section,
                }
            )

        return raw_chunks

    def _merge_short_chunks(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Gộp các chunk quá ngắn (< min_chunk_size) vào chunk liền kề."""
        if len(chunks) <= 1:
            return chunks

        merged: list[dict[str, Any]] = []
        carry = None

        for chunk in chunks:
            combined_text = f"{carry['text']}\n{chunk['text']}".strip() if carry else chunk['text']
            
            if len(combined_text) < self.min_chunk_size:
                carry = {"text": combined_text, "section_kind": chunk["section_kind"]}
            else:
                merged.append({"text": combined_text, "section_kind": chunk["section_kind"]})
                carry = None

        if carry:
            if merged:
                merged[-1]["text"] = f"{merged[-1]['text']}\n{carry['text']}".strip()
            else:
                merged.append(carry)

        return merged

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    SECTION_LABELS = {
        "case_summary": "Tóm tắt vụ án",
        "findings": "Nhận định của Toà án",
        "decision": "Quyết định",
        "header": "Phần đầu",
        "footer": "Phần cuối",
        "principle": "Nguyên tắc pháp lý",
    }

    @staticmethod
    def _safe_str(val: Any) -> str:
        if val is None:
            return ""
        try:
            if pd.isna(val):
                return ""
        except (TypeError, ValueError):
            pass
        return str(val).strip()

    def _extract_metadata(self, row: pd.Series) -> dict[str, Any]:
        """Trích metadata từ bản ghi anle_unified."""
        return {
            "doc_id": self._safe_str(row.get("doc_id", "")),
            "doc_code": self._safe_str(row.get("doc_code", "")),
            "title": self._safe_str(row.get("title", "")),
            "subject": self._safe_str(row.get("subject", "")),
            "case_type": self._safe_str(row.get("case_type", "")),
            "doc_type": self._safe_str(row.get("doc_type", "")),
            "court_level": self._safe_str(row.get("court_level", "")),
            "year": int(row.get("year", 0)),
            "jurisdiction": self._safe_str(row.get("jurisdiction", "")),
            "issuing_authority": self._safe_str(
                row.get("issuing_authority", "")
            ),
            "detail_url": self._safe_str(row.get("detail_url", "")),
            "applied_article_code": self._safe_str(
                row.get("applied_article_code", "")
            ),
            "applied_article_number": int(
                row.get("applied_article_number", 0)
            ),
            "applied_article_clause": self._safe_str(
                row.get("applied_article_clause", "")
            ),
        }

    def _build_context_prefix(
        self, metadata: dict[str, Any], section_kind: str
    ) -> str:
        """Tạo context prefix cho embed_text.

        Format: "[Loại vụ án] Tên bản án | Phần: Nhận định của Toà"
        """
        parts = []

        case_type = metadata.get("case_type", "")
        if case_type:
            parts.append(f"[{case_type}]")

        title = metadata.get("title", "")
        if title:
            parts.append(title)

        subject = metadata.get("subject", "")
        if subject:
            parts.append(f"({subject})")

        section_label = self.SECTION_LABELS.get(section_kind, section_kind)
        parts.append(f"| Phần: {section_label}")

        return " ".join(parts) + "\n"

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def process_document(
        self,
        doc_row: pd.Series,
        doc_sentences: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        """Xử lý 1 Án Lệ thành N Chunks."""
        metadata = self._extract_metadata(doc_row)
        doc_id = metadata["doc_id"]

        if doc_sentences.empty:
            return []

        # Bước 1: Gộp sentences → paragraphs
        paragraphs = self._assemble_paragraphs(doc_sentences)

        # Bước 2: Gộp paragraphs → chunks (theo section boundary)
        raw_chunks = self._group_paragraphs_into_chunks(paragraphs)
        
        # Bước 2.1: Merge chunk ngắn
        raw_chunks = self._merge_short_chunks(raw_chunks)

        if not raw_chunks:
            return []

        # Bước 2.5: Cắt nhỏ các chunk quá dài (do có paragraph cực dài)
        split_chunks: list[dict[str, Any]] = []
        for chunk in raw_chunks:
            if len(chunk["text"]) > self.max_chunk_size:
                sub_texts = self.text_splitter.split_text(chunk["text"])
                for sc in sub_texts:
                    sc = _clean_lead(sc)
                    if len(sc) >= 10:
                        split_chunks.append({
                            "text": sc,
                            "section_kind": chunk["section_kind"]
                        })
            else:
                split_chunks.append(chunk)

        # Bước 3: Gắn metadata + embed_text
        final_chunks: list[dict[str, Any]] = []
        for i, chunk in enumerate(split_chunks):
            section_kind = chunk["section_kind"]
            context_prefix = self._build_context_prefix(metadata, section_kind)

            final_chunks.append(
                {
                    "chunk_id": f"{doc_id}::chunk::{i}",
                    "chunk_index": i,
                    "chunk_type": section_kind,
                    "chunk_text": chunk["text"],
                    "embed_text": f"{context_prefix}{chunk['text']}",
                    "chunk_char_len": len(chunk["text"]),
                    "chunk_word_count": len(chunk["text"].split()),
                    **metadata,
                }
            )

        principle = self._safe_str(doc_row.get("principle_text", ""))
        if principle:
            context_prefix = self._build_context_prefix(metadata, "principle")
            final_chunks.insert(0, {
                "chunk_id": f"{doc_id}::chunk::principle",
                "chunk_index": -1,
                "chunk_type": "principle",
                "chunk_text": principle,
                "embed_text": f"[Nguyên tắc pháp lý] {context_prefix}{principle}",
                "chunk_char_len": len(principle),
                "chunk_word_count": len(principle.split()),
                **metadata,
            })

        total = len(final_chunks)
        for i, c in enumerate(final_chunks):
            c["chunk_index"] = i
            c["chunk_total"] = total

        return final_chunks

    # ------------------------------------------------------------------
    # Pipeline runner
    # ------------------------------------------------------------------

    def run(self) -> pd.DataFrame:
        """Chạy pipeline chunking end-to-end.

        Returns:
            DataFrame chứa tất cả chunks.
        """
        logger.info("Loading unified data from: %s", self.unified_path)
        unified_df = pd.read_parquet(self.unified_path)
        logger.info("Loading sentences data from: %s", self.sentences_path)
        sentences_df = pd.read_parquet(self.sentences_path)

        logger.info(
            "Total: %s documents, %s sentences",
            f"{len(unified_df):,}",
            f"{len(sentences_df):,}",
        )

        self.output_dir.mkdir(parents=True, exist_ok=True)
        out_jsonl = self.output_dir / "anle_chunks.jsonl"
        out_parquet = self.output_dir / "anle_chunks.parquet"

        # Pre-group sentences by doc_name for fast lookup
        sentences_grouped = dict(list(sentences_df.groupby("doc_name")))

        logger.info("Streaming chunks to %s ...", out_jsonl)
        total_chunks = 0
        failed_count = 0
        type_counts: dict[str, int] = {}
        chunk_sizes: list[int] = []

        with open(out_jsonl, "w", encoding="utf-8") as f:
            for _, row in tqdm(
                unified_df.iterrows(), total=len(unified_df), desc="Chunking Án Lệ"
            ):
                try:
                    doc_id = self._safe_str(row.get("doc_id", ""))
                    doc_sents = sentences_grouped.get(doc_id, pd.DataFrame())

                    chunks = self.process_document(row, doc_sents)
                    for chunk in chunks:
                        f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                        total_chunks += 1
                        ct = chunk.get("chunk_type", "unknown")
                        type_counts[ct] = type_counts.get(ct, 0) + 1
                        chunk_sizes.append(chunk["chunk_char_len"])
                except Exception as e:
                    logger.error(
                        "Failed on doc_id=%s: %s",
                        row.get("doc_id", "?"),
                        e,
                    )
                    failed_count += 1
                    continue

        if total_chunks == 0:
            logger.warning("⚠️ Không có chunk nào được tạo ra!")
            return pd.DataFrame()

        if failed_count > 0:
            logger.warning(
                "⚠️ %d/%d documents failed.", failed_count, len(unified_df)
            )

        # Thống kê
        logger.info(
            "Generated %s chunks from %s documents.",
            f"{total_chunks:,}",
            f"{len(unified_df):,}",
        )
        logger.info("Chunk types breakdown: %s", type_counts)

        if chunk_sizes:
            avg = sum(chunk_sizes) / len(chunk_sizes)
            sorted_s = sorted(chunk_sizes)
            median = sorted_s[len(sorted_s) // 2]
            logger.info(
                "Chunk size stats — avg: %d, median: %d, min: %d, max: %d chars",
                avg,
                median,
                min(chunk_sizes),
                max(chunk_sizes),
            )

        # Convert JSONL → Parquet
        logger.info("Converting JSONL to Parquet...")
        import pyarrow as pa
        import pyarrow.parquet as pq

        writer = None
        for batch in pd.read_json(out_jsonl, lines=True, chunksize=10_000):
            table = pa.Table.from_pandas(batch)
            if writer is None:
                writer = pq.ParquetWriter(str(out_parquet), table.schema)
            writer.write_table(table)

        if writer:
            writer.close()

        logger.info("Saved to %s", out_parquet)
        logger.info("✅ Án Lệ Chunking Pipeline Completed!")

        return pd.read_parquet(out_parquet)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    chunker = AnleChunker()
    result = chunker.run()

    if result is not None and len(result) > 0:
        print(f"\n📌 Dòng đầu tiên:")
        first = result.iloc[0]
        for col, val in first.items():
            print(f"  {col}: {str(val)[:200]}")
