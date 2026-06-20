# Mô Tả Dữ Liệu — Pháp Điển & Án Lệ

> Tài liệu giải thích cấu trúc, cách xử lý và lý do thiết kế cho 2 bộ dữ liệu pháp lý phục vụ hệ thống Graph RAG.

---

## 1. Tổng Quan

Hệ thống sử dụng **2 nguồn dữ liệu pháp lý** từ HuggingFace, được xử lý thành dạng phẳng (flat) thống nhất để phục vụ RAG indexing:

| Bộ dữ liệu | HuggingFace ID | Nội dung | Số lượng |
|-------------|----------------|----------|----------|
| **Pháp Điển** | `tmquan/phapdien-moj-gov-vn` | Toàn bộ hệ thống pháp luật Việt Nam (phapdien.moj.gov.vn) | 65,967 điều luật |
| **Án Lệ** | `tmquan/anle-toaan-gov-vn` | Án lệ từ Tòa án nhân dân tối cao (toaan.gov.vn) | 1,963 bản án |

**Mục tiêu chung:** Tải dữ liệu thô → chuẩn hóa → enrich metadata → xuất file JSONL/Parquet sẵn sàng cho embedding & indexing vào Neo4j Knowledge Graph.

---

## 2. Bộ Dữ Liệu Pháp Điển

### 2.1. Dữ liệu gốc (6 subsets trên HuggingFace)

```
tmquan/phapdien-moj-gov-vn
├── articles          — 65,967 dòng  ← BẢNG CHÍNH (mỗi dòng = 1 Điều luật)
├── subjects          — 202 dòng     (danh sách đề mục)
├── tree_nodes        — 245 dòng     (cấu trúc cây phân cấp)
├── ontology_topics   — 42 dòng      (42 chủ đề pháp luật)
├── ontology_subjects — 202 dòng     (202 đề mục + tên EN)
└── ontology_glossary — 116 dòng     (thuật ngữ pháp lý VI/EN)
```

#### Quan hệ giữa các subsets

```
ontology_topics (42 chủ đề)
    │
    │ 1 topic → N subjects (qua topic_id)
    ▼
ontology_subjects (202 đề mục)
    │
    │ 1 subject → N articles (qua subject_id)
    ▼
articles (65,967 điều luật)  ← bảng chính, chứa nội dung điều luật
```

- **`articles`**: Bảng chính, mỗi dòng = 1 Điều luật với nội dung toàn văn, metadata phân cấp (topic_id, subject_id, chapter_title), và source_links (link đến VBPL gốc).
- **`ontology_topics`**: 42 chủ đề lớn (VD: "Hình sự", "Dân sự", "Đất đai"), có tên tiếng Anh và ghi chú.
- **`ontology_subjects`**: 202 đề mục chi tiết (VD: "Bộ luật Hình sự 2015"), có tên tiếng Anh.
- **`subjects`**: Metadata **scrape thô** của 202 đề mục, lấy trực tiếp từ giao diện web pháp điển (`ViewBoPD.aspx`). Chỉ có thông tin tiếng Việt nguyên bản.
- **`ontology_subjects`**: Cũng là 202 đề mục (cùng `subject_id`), nhưng đã được **tác giả dataset curate thủ công**: bổ sung tên tiếng Anh (`subject_title_en`), chuẩn hóa tên tiếng Việt. Đây là phần ontology song ngữ Việt–Anh.
- → **Khác biệt chính**: `subjects` = raw từ web (chỉ VI), `ontology_subjects` = curated bởi tác giả (VI + EN). Trong pipeline, ta dùng `ontology_subjects` để enrich (lấy tên EN), còn `subjects` lưu riêng cho Phase 4 (tạo Subject nodes với metadata gốc).
- **`tree_nodes`**: 245 node mô tả cây phân cấp (parent → child), dùng cho Phase 4 (Graph Construction).
- **`ontology_glossary`**: 116 thuật ngữ pháp lý (VD: "Nghị định" = "Decree"), do tác giả dataset dịch thủ công, dùng cho NER và query expansion.

### 2.2. Quy trình xử lý

```
articles (65K) ──┐
                 │
ontology_topics ─┤── Enrich ──→ Format ──→ phapdien_unified.jsonl
                 │
ontology_subjects┘
```

#### Bước 1: Ontology Enrichment (`PhapdienOntologyEnricher`)

**Làm gì:** Bổ sung thông tin từ ontology vào bảng articles.

**Cụ thể:**
- Tra cứu `topic_id` → lấy `topic_title_en` (tên EN), `topic_note` (ghi chú) từ `ontology_topics`
- Tra cứu `subject_id` → lấy `subject_title_en` (tên EN) từ `ontology_subjects`
- Chuẩn hóa tên tiếng Việt: ưu tiên tên từ ontology, nếu không có thì fallback về tên trong articles

**Tại sao:**
- Bảng `articles` gốc chỉ có `topic_id` và `subject_id`, **không có tên tiếng Anh** → cần JOIN để RAG có thể xử lý đa ngôn ngữ
- Tên tiếng Việt trong `articles` có thể không chuẩn (do scraping) → ontology là nguồn chuẩn hóa hơn, nên ưu tiên ontology
- Ghi chú chủ đề (`topic_note`) cung cấp context bổ sung cho embedding

#### Bước 2: Data Formatting (`PhapdienDataFormatter`)

**Làm gì:** Chuyển đổi DataFrame đã enrich thành schema chuẩn.

**Cụ thể:**
1. **Serialize `source_links`**: Cột `source_links` trong dataset gốc là kiểu **`list[dict]`** (nested), mỗi dict chứa 2 key:
   - `text`: Tên + số hiệu VBPL gốc (VD: `"(Điều 1 Luật số 32/2004/QH11 An ninh Quốc gia ngày 03/12/2004 của Quốc hội...)"`).
   - `href`: Link trực tiếp đến điều tương ứng trên `vbpl.vn` — Cơ sở dữ liệu pháp luật quốc gia (VD: `"http://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=18562#Chuong_I_Dieu_1"`).
   - Ví dụ raw: `[{"text": "(Điều 1 Luật số 32/2004/QH11...)", "href": "http://vbpl.vn/..."}]`
   - Sau serialize: `'[{"text": "(Điều 1 Luật số 32/2004/QH11...)", "href": "http://vbpl.vn/..."}]'` (cùng nội dung, nhưng kiểu `str` thay vì `list`).
   - Một Điều có thể trích từ **nhiều VBPL** (Luật gốc + Luật sửa đổi), nên đây là mảng.
   - **Lưu ý kỹ thuật**: Khi HuggingFace `.to_pandas()`, cột này trở thành `numpy.ndarray` chứ không phải `list` → code serialize cần handle cả hai kiểu.
2. **Tạo `hierarchy_path`**: Ghép đường dẫn phân cấp: `"Chủ đề > Đề mục > Chương > Điều"`. VD: `"Hình sự > Bộ luật Hình sự 2015 > Chương XIV > Điều 173. Tội trộm cắp tài sản"`.
3. **Tạo `metadata_json`**: Đóng gói metadata phụ (article_anchor, tên gốc trước chuẩn hóa) vào 1 cột JSON.
4. **Fill NaN**: Cột string → `""`, cột số → `0`.

**Tại sao:**
- `source_links` là nested structure → không lưu được trực tiếp vào CSV dạng phẳng → serialize thành JSON string để đồng nhất output format
- `hierarchy_path` phục vụ RAG: khi embedding, prefix bằng hierarchy giúp model hiểu ngữ cảnh (Điều luật này thuộc lĩnh vực nào)
- `metadata_json` giữ lại thông tin phụ mà không phình schema chính (nguyên tắc: schema gọn, metadata linh hoạt)
- Fill NaN tránh lỗi downstream khi serialize/embed

### 2.3. Schema output (`phapdien_unified`) — 23 cột

| Cột | Kiểu | Mô tả | Nguồn |
|-----|------|-------|-------|
| `doc_id` | string | ID duy nhất (= record_id gốc) | articles.record_id |
| `article_id` | string | Mã trích dẫn phân cấp (VD: "Điều 1.1.LQ.1") | articles |
| `article_title` | string | Tên điều (VD: "Điều 1. Nước CHXHCN VN...") | articles |
| `chapter_title` | string | Tên chương chứa điều này | articles |
| `topic_id` | string | ID chủ đề | articles |
| `topic_number` | int | Số thứ tự chủ đề (1–42) | articles |
| `topic_title_vi` | string | Tên chủ đề tiếng Việt (đã chuẩn hóa) | ontology (ưu tiên) → articles (fallback) |
| `topic_title_en` | string | Tên chủ đề tiếng Anh | ontology_topics |
| `topic_note` | string | Ghi chú chủ đề | ontology_topics |
| `subject_id` | string | ID đề mục | articles |
| `subject_number` | int | Số thứ tự đề mục | articles |
| `subject_title_vi` | string | Tên đề mục tiếng Việt (đã chuẩn hóa) | ontology (ưu tiên) → articles (fallback) |
| `subject_title_en` | string | Tên đề mục tiếng Anh | ontology_subjects |
| `content_text` | string | **Toàn văn Điều luật** — nội dung chính cho RAG | articles |
| `content_char_len` | int | Số ký tự nội dung | articles |
| `content_word_count` | int | Số từ nội dung | articles |
| `source_note_text` | string | Ghi chú nguồn (VD: "Theo Luật số 45/2019/QH14") | articles |
| `related_note_text` | string | Ghi chú liên quan | articles |
| `source_links_json` | string | JSON array các link **ngược về VBPL gốc** trên `vbpl.vn` (văn bản pháp luật gốc mà Điều này được trích từ đó). VD: `[{"text": "(Điều 1 Luật số 32/2004/QH11...)", "href": "http://vbpl.vn/..."}]` | articles.source_links (serialized) |
| `source_url` | string | URL đến **chính Điều luật này** trên trang Pháp Điển `phapdien.moj.gov.vn` (nơi nội dung đã được pháp điển hóa, tổng hợp theo hệ thống Chủ đề → Đề mục → Chương → Điều) | articles |
| `hierarchy_path` | string | Đường dẫn phân cấp đầy đủ (tự tạo) | Computed |
| `scraped_at` | string | Thời gian thu thập dữ liệu gốc | articles |
| `metadata_json` | string | JSON chứa metadata phụ | Computed |

### 2.4. Các file output phụ trợ (auxiliary)

| File | Nguồn | Vai trò trong pipeline |
|------|-------|----------------------|
| `phapdien_glossary` | ontology_glossary | Phase 3: dictionary cho NER; Phase 5: embed thuật ngữ |
| `phapdien_tree_nodes` | tree_nodes | Phase 4: tạo cây phân cấp trong graph |
| `phapdien_ontology_topics` | ontology_topics | Phase 4: tạo Topic nodes |
| `phapdien_subjects` | subjects | Phase 4: tạo Subject nodes + metadata |

---

## 3. Bộ Dữ Liệu Án Lệ

### 3.1. Dữ liệu gốc (4 subsets, chỉ dùng 2)

```
tmquan/anle-toaan-gov-vn
├── documents  — 1,963 dòng  ← BẢNG CHÍNH (mỗi dòng = 1 bản án/án lệ)
├── sentences  — 273,379 dòng (câu đã tách sẵn)
├── embed      — 1,963 dòng  ← BỎ QUA (embeddings pre-computed)
└── reduce     — 1,963 dòng  ← BỎ QUA (tọa độ 2D cho visualization)
```

**Tại sao chỉ tải 2 subsets?**
- `embed` và `reduce` là kết quả pre-computed của tác giả dataset (embeddings, PCA/t-SNE coordinates) → **ta sẽ tự tính embedding** bằng model phù hợp (VD: bge-m3) trong Phase 5, nên không cần dùng lại
- `documents` là bảng chính chứa toàn văn án lệ
- `sentences` là phiên bản tách câu, hữu ích cho chunking ở Phase 2

### 3.2. Quy trình xử lý

```
documents (1,963) ──→ Format ──→ anle_unified.jsonl
sentences (273K)  ──→ Clean  ──→ anle_sentences.jsonl (auxiliary)
```

#### Xử lý đơn giản hơn Pháp Điển vì:
- Án Lệ **không có hệ thống ontology phân cấp** (không có topics → subjects → articles)
- Mỗi bản án là 1 document độc lập, đã có đầy đủ metadata (tên tòa, loại vụ, năm, cấp tòa...)
- → Không cần bước Enrichment, chỉ cần Format (đổi tên cột, xử lý NaN, đóng gói metadata)

#### Chi tiết xử lý (`AnleDataFormatter`):
1. **Đổi tên cột**: `doc_name` → `doc_id`, `markdown` → `content_markdown`, `char_len` → `content_char_len` (thống nhất naming convention)
2. **Tạo `metadata_json`**: Đóng gói `text_hash` và `parser_model` vào JSON (thông tin kỹ thuật, không cần thiết cho RAG nhưng cần cho traceability)
3. **Fill NaN**: Cột string → `""`, cột số → `0`, confidence → `0.0`

### 3.3. Schema output (`anle_unified`) — 30 cột

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `doc_id` | string | ID bản án (VD: "TAND192001") |
| `doc_code` | string | Mã văn bản (VD: "38/2021/DS-PT") |
| `precedent_number` | string | Số án lệ (VD: "Án lệ số 01/2016") |
| `title` | string | Tiêu đề bản án |
| `subject` | string | Chủ đề vụ án |
| `case_type` | string | Loại vụ án (hình sự, dân sự, hành chính...) |
| `doc_type` | string | Loại văn bản (bản án, quyết định...) |
| `doc_subtype` | string | Phân loại phụ |
| `year` | int | Năm ban hành |
| `issue_date` | string | Ngày ban hành |
| `adopted_date` | string | Ngày được thông qua làm án lệ |
| `issuing_authority` | string | Cơ quan ban hành |
| `court_level` | string | Cấp tòa án (trung ương, tỉnh, huyện) |
| `jurisdiction` | string | Thẩm quyền xét xử |
| `applied_article_code` | string | Mã bộ luật được áp dụng (VD: "BLHS") |
| `applied_article_number` | int | Số điều luật được áp dụng |
| `applied_article_clause` | int | Số khoản được áp dụng |
| `principle_text` | string | **Nguyên tắc pháp lý** rút ra từ án lệ |
| `content_markdown` | string | **Toàn văn bản án** (markdown) — nội dung chính |
| `content_char_len` | int | Số ký tự nội dung |
| `num_pages` | int | Số trang |
| `num_sections` | int | Số mục/phần |
| `num_paragraphs` | int | Số đoạn văn |
| `num_sentences` | int | Số câu |
| `detail_url` | string | URL chi tiết trên toaan.gov.vn |
| `pdf_url` | string | URL file PDF gốc |
| `source` | string | Nguồn dữ liệu |
| `structure_json` | string | Cấu trúc bản án (JSON) |
| `extracted_json` | string | Thông tin trích xuất (JSON) |
| `parsed_at` | string | Thời gian parse dữ liệu |
| `confidence` | float | Độ tin cậy của quá trình parse |
| `metadata_json` | string | Metadata phụ (text_hash, parser_model) |

### 3.4. File phụ trợ: `anle_sentences`

Bảng `sentences` (273,379 dòng) lưu riêng, mỗi dòng = 1 câu đã tách từ bản án. Bao gồm: nội dung câu, vị trí trong bản án (page, paragraph, index), metadata liên kết về bản án gốc.

**Vai trò:** Sử dụng trong Phase 2 (Chunking) — có thể dùng các câu đã tách sẵn thay vì tự tách, đảm bảo ranh giới câu chính xác.

---

## 4. So Sánh 2 Bộ Dữ Liệu

| Tiêu chí | Pháp Điển | Án Lệ |
|----------|-----------|-------|
| **Bản chất** | Điều luật (quy phạm) | Bản án (thực tiễn) |
| **Số lượng** | 65,967 điều | 1,963 bản án |
| **Độ dài trung bình** | Ngắn (vài trăm từ/điều) | Dài (hàng nghìn từ/bản án) |
| **Có ontology phân cấp** | ✅ (Topic → Subject → Chapter → Article) | ❌ (flat, mỗi án lệ độc lập) |
| **Cần enrichment** | ✅ (JOIN ontology để lấy tên EN, ghi chú) | ❌ (metadata đã đầy đủ) |
| **Liên kết chéo** | `source_links` → VBPL gốc | `applied_article_*` → Điều luật |
| **Nội dung chính** | `content_text` (plain text) | `content_markdown` (markdown) |
| **Subsets phụ** | glossary, tree_nodes, topics, subjects | sentences |

---

## 5. Tại Sao Xử Lý Như Vậy — Giải Thích Thiết Kế

### 5.1. Tại sao flatten thành 1 file unified?

**Vấn đề:** Dữ liệu gốc trên HuggingFace nằm rải rác ở nhiều subsets (6 cho Pháp Điển, 4 cho Án Lệ). Nếu giữ nguyên, các phase sau (chunking, embedding, indexing) phải tự JOIN nhiều bảng → phức tạp và dễ lỗi.

**Giải pháp:** JOIN sẵn tất cả thông tin cần thiết vào 1 bảng phẳng → downstream chỉ cần đọc 1 file.

**Nguyên tắc:** *"Denormalize early, normalize in graph"* — giai đoạn tiền xử lý thì flatten cho dễ xử lý, còn cấu trúc phân cấp sẽ được tái tạo trong Knowledge Graph (Phase 4).

### 5.2. Tại sao giữ lại các file auxiliary?

Mặc dù unified đã flatten, các bảng phụ vẫn cần thiết cho các phase sau:
- `tree_nodes` → tạo cây phân cấp trong graph (HAS_CHILD edges)
- `glossary` → dictionary cho NER (Phase 3) + embed thuật ngữ (Phase 5)
- `ontology_topics` → tạo Topic nodes trong graph (Phase 4)
- `subjects` → tạo Subject nodes với metadata đầy đủ

### 5.3. Tại sao ưu tiên tên từ ontology hơn articles?

Bảng `articles` gốc có `topic_title_vi` và `subject_title_vi` nhưng đây là dữ liệu scrape từ web → có thể không chuẩn (thiếu dấu, viết tắt, lỗi encoding). Bảng `ontology_*` là dữ liệu đã curated → chuẩn hơn. Logic: lấy ontology trước, nếu trống thì fallback về articles.

### 5.4. Tại sao bỏ qua embed và reduce của Án Lệ?

- `embed`: Vector embeddings pre-computed bởi tác giả dataset, nhưng ta không biết model nào, dimension nào → **không tái sử dụng được** vì ta cần embedding nhất quán giữa Pháp Điển và Án Lệ (cùng 1 model, cùng vector space)
- `reduce`: Tọa độ 2D (PCA/t-SNE/UMAP) cho visualization → không liên quan đến RAG pipeline

### 5.5. Tại sao serialize source_links thành JSON string?

`source_links` trong bảng articles gốc là kiểu nested `list[dict]`, mỗi dict chứa `{"text": "...", "href": "..."}` — link ngược về văn bản pháp luật gốc trên `vbpl.vn`.

**Phân biệt `source_links_json` vs `source_url`:**

```
Luật số 32/2004/QH11 (văn bản gốc trên vbpl.vn)
    ▲
    │  source_links_json.href trỏ ngược VỀ ĐÂY
    │
Điều 1.1.LQ.1 (đã pháp điển hóa trên phapdien.moj.gov.vn)
    │
    │  source_url trỏ đến ĐÂY
    ▼
```

| Trường | Website | Ý nghĩa |
|--------|---------|----------|
| `source_url` | `phapdien.moj.gov.vn` | Link đến Điều luật **đã pháp điển** (đã tổng hợp vào hệ thống) |
| `source_links_json` | `vbpl.vn` | Link ngược về **văn bản pháp luật gốc** mà Điều này được trích từ đó |

→ `source_url` luôn là **1 link** (trang Pháp Điển), còn `source_links_json` có thể là **mảng nhiều link** (1 Điều có thể trích từ nhiều VBPL: luật gốc + luật sửa đổi).

**Tại sao serialize?**
- CSV không hỗ trợ nested data → serialize để đồng nhất output format
- Downstream (Neo4j import) cần string → parse lại khi cần
- Giữ schema phẳng (flat) → dễ debug, inspect, và xử lý

**Lưu ý kỹ thuật (bug đã fix):** Khi HuggingFace `.to_pandas()`, cột `source_links` trở thành `numpy.ndarray` thay vì `list`. Code serialize ban đầu chỉ check `isinstance(value, list)` → bỏ sót toàn bộ 65,967 bản ghi. Đã fix bằng cách thêm check `hasattr(value, "tolist")` để handle cả `numpy.ndarray`.

### 5.6. Tại sao tạo hierarchy_path?

`hierarchy_path` = `"Chủ đề > Đề mục > Chương > Điều"` phục vụ 2 mục đích:
1. **Embedding context**: Khi embed chunk, prefix bằng hierarchy_path giúp model hiểu ngữ cảnh (điều luật này thuộc lĩnh vực nào)
2. **Display**: Hiển thị cho user khi trả kết quả RAG, giúp user biết điều luật nằm ở đâu trong hệ thống pháp luật

---

## 6. Cấu Trúc Thư Mục Output

```
backend/src/knowlegde_data/
├── phapdien/
│   ├── phapdien_unified.jsonl          ← 65,967 điều (bộ chính cho RAG)
│   ├── phapdien_unified.parquet        ← cùng data, format Parquet
│   ├── phapdien_glossary.jsonl         ← 116 thuật ngữ
│   ├── phapdien_tree_nodes.jsonl       ← 245 nodes cây phân cấp
│   ├── phapdien_ontology_topics.jsonl  ← 42 chủ đề
│   └── phapdien_subjects.jsonl         ← 202 đề mục
└── anle/
    ├── anle_unified.jsonl              ← 1,963 án lệ (bộ chính cho RAG)
    ├── anle_unified.parquet
    └── anle_sentences.jsonl            ← 273,379 câu (cho chunking)
```

---

## 7. Cách Sử Dụng

```python
# --- Pháp Điển ---
from knowledge_processing.phapdien_load_dataset import PhapdienDatasetLoader

loader = PhapdienDatasetLoader()
unified_df = loader.run()  # load → enrich → format → save → report
# unified_df: DataFrame 65,967 rows × 23 columns

# --- Án Lệ ---
from knowledge_processing.anle_load_dataset import AnleDatasetLoader

loader = AnleDatasetLoader()
unified_df = loader.run()  # load → format → save → report
# unified_df: DataFrame 1,963 rows × 30 columns
```
