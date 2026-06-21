"""
Extraction Schema (Phase 3)
===========================

Pydantic schema cho structured output khi trích xuất Entity & Relation
bằng LLM (Gemini). Dùng với LangChain ``with_structured_output``.

Bộ loại Entity & Relation bám theo graph_rag_pipeline.md (Phase 3).
"""

from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Loại thực thể pháp lý."""

    VBPL = "VBPL"                      # Văn bản pháp luật: "Luật số 32/2004/QH11"
    DIEU = "DIEU"                      # Điều luật: "Điều 173", "khoản 2 Điều 8"
    CO_QUAN = "CO_QUAN"               # Cơ quan: "Bộ Tư pháp", "UBND tỉnh"
    KHUNG_HINH_PHAT = "KHUNG_HINH_PHAT"  # "phạt tù từ 3-7 năm"
    LINH_VUC = "LINH_VUC"            # Lĩnh vực: "đất đai", "hình sự"
    THOI_GIAN = "THOI_GIAN"          # "2015", "ngày 01/01/2020"
    CHU_THE = "CHU_THE"              # "người lao động", "người sử dụng đất"


class RelationType(str, Enum):
    """Loại quan hệ giữa các thực thể."""

    TRICH_DAN = "TRICH_DAN"   # Điều A dẫn chiếu Điều/VBPL B
    SUA_DOI = "SUA_DOI"       # VB mới sửa đổi VB cũ
    HUONG_DAN = "HUONG_DAN"   # VB hướng dẫn thi hành VB khác
    THAY_THE = "THAY_THE"     # VB mới thay thế VB cũ
    LIEN_QUAN = "LIEN_QUAN"   # Liên kết chung
    THUOC = "THUOC"           # Entity thuộc phạm vi (Điều THUOC VBPL, cơ quan THUOC cơ quan)


class ExtractedEntity(BaseModel):
    """Một thực thể được trích xuất từ đoạn văn bản."""

    name: str = Field(
        description="Tên thực thể, giữ NGUYÊN VĂN như xuất hiện trong văn bản. "
        "VD: 'Luật số 32/2004/QH11', 'Điều 173', 'Bộ Tư pháp'."
    )
    type: EntityType = Field(description="Loại thực thể.")


class ExtractedRelation(BaseModel):
    """Một quan hệ giữa hai thực thể."""

    source: str = Field(description="Tên thực thể nguồn (khớp 'name' trong entities).")
    target: str = Field(description="Tên thực thể đích (khớp 'name' trong entities).")
    type: RelationType = Field(description="Loại quan hệ.")


class ExtractionResult(BaseModel):
    """Kết quả trích xuất cho 1 chunk: danh sách entity + relation."""

    entities: List[ExtractedEntity] = Field(
        default_factory=list, description="Các thực thể tìm thấy trong đoạn văn."
    )
    relations: List[ExtractedRelation] = Field(
        default_factory=list,
        description="Các quan hệ giữa thực thể. Chỉ trích quan hệ được nêu RÕ "
        "trong văn bản, không suy diễn.",
    )
