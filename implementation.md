# Kế hoạch triển khai Phase 2: Chunking cho Pháp Điển

Mục tiêu của Phase này là chia nhỏ nội dung của 65,967 Điều luật (cột `content_text` trong `phapdien_unified.jsonl`) thành các đoạn (chunk) ngắn hơn, giúp mô hình Embedding và Vector Search hoạt động chính xác.

## 1. Mục Tiêu & Input/Output
* **Input**: `backend/knowlegde_data/phapdien/phapdien_unified.jsonl`
* **Output**: `backend/knowlegde_data/phapdien/phapdien_chunks.jsonl`
* **File Code**: `backend/src/knowledge_processing/phapdien_chunker.py`

## 2. Chiến lược Chunking (Semantic Legal Chunking)

Đặc thù văn bản luật Việt Nam thường theo cấu trúc phân cấp: **Điều** → **Khoản** (đánh số 1, 2, 3...) → **Điểm** (đánh chữ a, b, c...). Vì vậy, thay vì cắt ngang ký tự mù quáng, chúng ta sẽ áp dụng **Hybrid Chunking**:

### Bước 1: Khoản-level Chunking (Rule-based)
Dùng Regex để nhận diện ranh giới các "Khoản" bên trong một "Điều".
* **Regex Pattern**: `r'(?:^|\n)\s*(\d+)\.\s+'` (Tìm các đoạn bắt đầu bằng số theo sau là dấu chấm, ví dụ: "1. ", "2. ")
* Lợi ích: Giữ trọn vẹn ngữ nghĩa của một quy định cụ thể. Mỗi chunk sẽ tương ứng với 1 Khoản.

### Bước 2: LangChain Fallback (Sliding Window)
Với những Điều luật không chia Khoản, hoặc có Khoản quá dài (vượt quá 800 - 1000 ký tự), ta sẽ dùng `RecursiveCharacterTextSplitter` của LangChain để cắt nhỏ với một overlap nhất định để không mất context.
* **chunk_size**: 1000 ký tự
* **chunk_overlap**: 150 ký tự

## 3. Metadata đi kèm Chunk

Khi đưa vào Neo4j (Graph Database), mỗi Node `Chunk` phải gắn liền với Node `Article` gốc. Do đó, mỗi chunk sẽ được giữ nguyên metadata của Điều luật:
```json
{
  "chunk_id": "07e896d5a9003e01_chunk_1", 
  "doc_id": "07e896d5a9003e01",
  "article_id": "Điều 1.1.LQ.1",
  "hierarchy_path": "An ninh quốc gia > ... > Điều 1",
  "chunk_text": "1. Người nào trộm cắp...",
  "chunk_index": 1,
  "chunk_type": "khoan", // hoặc "split", "full"
  "chunk_char_len": 450,
  "chunk_word_count": 92,
  "chunk_total": 3
}
```

## 4. Tổng Kết Phân Tích Thực Tế

Sau khi áp dụng chiến lược trên cho 65,967 Điều luật:
- **Tách theo Khoản (`khoan`)**: Phổ biến nhất, đảm bảo tính Semantic cực mạnh.
- **Giữ nguyên Điều (`full`)**: Các Điều luật ngắn không chia Khoản.
- **Fallback cắt nhỏ (`split`)**: Chỉ xảy ra với các đoạn siêu dài.
