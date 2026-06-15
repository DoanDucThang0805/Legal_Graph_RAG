# Codex Task Prompts tiếng Việt v2 — Legal Graph RAG

> File liên quan trực tiếp: `legal_rag_phase_plan_v3.md`  
> Cách dùng: chọn đúng `Task ID` trong plan, copy prompt tương ứng vào Codex.  
> Quy tắc quan trọng: **Codex không chạy lệnh. Codex chỉ sửa code và đưa lệnh để người dùng tự chạy.**

---

# GLOBAL — Prompt nền cho mọi phiên Codex

```text
Bạn đang code trong repository Legal_Graph_RAG.

Trước khi code, hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/01_project_architecture.md
- skills/11_code_quality_testing.md

Mục tiêu project:
Xây dựng hệ thống Vietnamese Legal RAG cho bài toán truy hồi và hỏi đáp pháp luật tiếng Việt.

Nguyên tắc bắt buộc:
1. LLM không được tự quyết định relevant_docs hoặc relevant_articles.
2. relevant_docs và relevant_articles chỉ được sinh từ canonical legal_articles registry.
3. phapdien chỉ là nguồn retrieval, không phải nguồn citation chính thức.
4. anle chỉ là nguồn phụ trợ reasoning, không phải nguồn citation chính thức.
5. Code phải rõ ràng, có type hints, có comment tiếng Việt cho logic phức tạp.
6. Scripts chỉ là entrypoint mỏng. Business logic phải nằm trong backend modules.
7. Không triển khai phase/task ngoài phạm vi được giao.
8. Không hard-code path; phải dùng config.
9. Phải có validation và logging cho dữ liệu lỗi.
10. Ưu tiên hàm nhỏ, dễ test, dễ debug.
11. Không chạy lệnh trong terminal thay người dùng. Chỉ liệt kê lệnh để người dùng tự chạy.

Task ID hiện tại:
[DÁN TASK ID Ở ĐÂY]

Quy trình báo cáo bắt buộc:

TRƯỚC KHI SỬA CODE, hãy trình bày và dừng lại chờ tôi xác nhận:
- Scope bạn hiểu
- Files dự kiến sửa
- Test command sẽ chạy / đề xuất tôi chạy

Chỉ bắt đầu sửa code sau khi tôi xác nhận, trừ khi tôi ghi rõ: "triển khai luôn".

SAU KHI HOÀN THÀNH, hãy báo cáo:
- Files changed
- Logic thay đổi
- Acceptance Criteria đã đạt/chưa đạt
- Test result
- Risk còn lại

Lưu ý về test result:
- Bạn không tự chạy lệnh thay tôi.
- Nếu chưa có log từ tôi, hãy ghi rõ: "Chưa chạy — người dùng cần chạy các lệnh bên dưới".
- Nếu tôi cung cấp log test, hãy tóm tắt pass/fail theo log đó.

Yêu cầu output cuối cùng của bạn:
- Files changed.
- Logic thay đổi.
- Acceptance Criteria đã đạt/chưa đạt.
- Test result.
- Risk còn lại.
- Lệnh tôi cần tự chạy để test/validate.
- Expected outputs.
```

---

# CONTROL.PROTOCOL — Quy trình kiểm soát bắt buộc

Dán kèm section này nếu muốn ép Codex làm theo quy trình review trước khi sửa code.

```text
Trước khi sửa code, hãy trình bày:

1. Scope bạn hiểu
- Bạn hiểu task này cần làm gì?
- Không làm gì ngoài scope?

2. Files dự kiến sửa
- Liệt kê file sẽ tạo/sửa.
- Nếu cần sửa file ngoài danh sách, phải giải thích lý do trước.

3. Test command sẽ chạy / đề xuất người dùng chạy
- Liệt kê lệnh test/validation tương ứng.
- Không tự chạy lệnh thay người dùng.

Sau khi trình bày 3 mục trên, hãy dừng lại và chờ tôi xác nhận.
Chỉ sửa code khi tôi trả lời "OK", "triển khai", hoặc "triển khai luôn".

Sau khi hoàn thành, báo cáo:

1. Files changed
- Liệt kê file đã tạo/sửa.

2. Logic thay đổi
- Tóm tắt thay đổi chính.

3. Acceptance Criteria đã đạt/chưa đạt
- Dùng checklist [x] / [ ].
- Nếu AC nào chưa đạt, nói rõ lý do.

4. Test result
- Nếu chưa chạy test: ghi "Chưa chạy — người dùng cần chạy lệnh bên dưới".
- Nếu người dùng cung cấp log test: tóm tắt pass/fail.

5. Risk còn lại
- Nêu rủi ro kỹ thuật, dữ liệu, performance hoặc assumptions còn lại.
```

---

# P0.T1 — Tạo skeleton project

```text
Task ID: P0.T1

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/01_project_architecture.md
- skills/11_code_quality_testing.md

Chỉ triển khai P0.T1: tạo skeleton project.

Nhiệm vụ:
1. Tạo các thư mục:
   - backend/config
   - backend/infrastructure
   - backend/schema
   - backend/knowledge_processing
   - backend/indexing
   - backend/query_analysis
   - backend/retrieval
   - backend/qa
   - backend/evaluation
   - backend/submission
   - scripts
   - data/raw
   - data/processed
   - data/outputs
   - tests

2. Thêm __init__.py cho các Python package.

Không làm:
- Không tạo logic data loading.
- Không tạo retrieval.
- Không tạo QA/submission.
- Không chạy lệnh.

Acceptance Criteria:
- Tất cả folder mục tiêu tồn tại.
- Các Python package có __init__.py.
- Không xóa file hiện có nếu không cần.
- `python -c "import backend"` sẽ chạy được khi người dùng tự chạy.

Sau khi code xong, hãy trả lại:
- File/folder đã tạo.
- Checklist AC.
- Lệnh để người dùng tự chạy:
  python -c "import backend; print('backend import ok')"
  find backend -maxdepth 2 -type f | sort
```

---

# P0.T2 — Config và settings

```text
Task ID: P0.T2

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/01_project_architecture.md
- skills/11_code_quality_testing.md

Chỉ triển khai P0.T2: config và settings.

Tạo/sửa:
- backend/config/settings.py
- backend/config/path_config.py
- backend/config/retrieval_config.yaml
- backend/config/model_config.yaml
- .env.example

Yêu cầu:
- Có function get_settings().
- Có path config cho raw_dir, processed_dir, output_dir.
- Có model config cho embedding_model và generator_model.
- Có retrieval config cho top_k, rrf_k, max_articles.
- Không hard-code path trong business logic.
- Không chứa secret thật trong .env.example.
- Không chạy lệnh.

Acceptance Criteria:
- Config load được từ Python.
- YAML đọc được.
- Có default config hợp lý cho Phase 1–5.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.config.settings import get_settings
s = get_settings()
print(s)
PY
```

---

# P0.T3 — Docker compose baseline

```text
Task ID: P0.T3

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/01_project_architecture.md
- skills/11_code_quality_testing.md

Chỉ triển khai P0.T3: docker-compose baseline.

Tạo/sửa:
- docker-compose.yml
- .env.example nếu cần thêm biến môi trường

Services tối thiểu:
- qdrant
- opensearch
- neo4j
- postgres optional

Yêu cầu:
- Có persistent volume cho services quan trọng.
- Có ports rõ ràng.
- Có environment config an toàn.
- Neo4j chỉ để sẵn cho Phase 8, chưa dùng ở Phase 1.
- Không chạy docker command.

Acceptance Criteria:
- docker-compose.yml hợp lệ.
- Có qdrant và opensearch.
- Có neo4j service.

Lệnh người dùng tự chạy:
docker compose config
docker compose up -d qdrant opensearch
docker compose ps
```

---

# P1.T1 — Schema Pydantic

```text
Task ID: P1.T1

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/02_data_loading_huggingface.md
- skills/04_canonical_article_registry.md
- skills/11_code_quality_testing.md

Chỉ triển khai P1.T1: schema Pydantic.

Tạo/sửa:
- backend/schema/question.py
- backend/schema/legal_document.py
- backend/schema/legal_article.py
- backend/schema/phapdien_article.py
- backend/schema/anle_unit.py
- backend/schema/retrieval_result.py
- backend/schema/submission.py

Yêu cầu bắt buộc:
- LegalArticle có fields:
  article_id, law_id, law_title, article_no, article_title, article_text, source_url, domain, status.
- LegalArticle có property relevant_article_string.
- LegalArticle có property relevant_doc_string.
- SubmissionItem schema phản ánh format results.json.
- Có type hints.
- Không chạy lệnh.

Acceptance Criteria:
- Import được tất cả schema.
- LegalArticle tạo ra đúng citation strings.
- Không có dependency sang retrieval/QA.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.schema.legal_article import LegalArticle
a = LegalArticle(
    article_id="04/2017/QH14|Luật 04/2017/QH14 Luật Hỗ trợ doanh nghiệp nhỏ và vừa|Điều 4",
    law_id="04/2017/QH14",
    law_title="Luật 04/2017/QH14 Luật Hỗ trợ doanh nghiệp nhỏ và vừa",
    article_no="Điều 4",
    article_text="Nội dung điều luật..."
)
print(a.relevant_article_string)
print(a.relevant_doc_string)
PY
```

---

# P1.T2 — Text normalization

```text
Task ID: P1.T2

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/03_legal_normalization.md
- skills/11_code_quality_testing.md

Chỉ triển khai P1.T2: text normalization.

Tạo/sửa:
- backend/knowledge_processing/normalize_text.py
- backend/knowledge_processing/normalize_legal_doc.py
- tests/test_normalize_text.py

Functions cần có:
- normalize_vietnamese_text(text: str | None) -> str
- normalize_article_no(article_no: str | None) -> str
- normalize_law_id(value: str | None) -> str
- normalize_law_title(law_type: str | None, law_id: str | None, title: str | None) -> str

Rules:
- Unicode NFC.
- NBSP -> space thường.
- Gộp khoảng trắng lặp.
- Xử lý None an toàn.
- "Điều 04." -> "Điều 4".
- "điều 7a" -> "Điều 7a".
- Không lower-case toàn bộ text pháp luật.
- Không chạy lệnh.

Acceptance Criteria:
- Có pytest cho các case chính.
- Các function import được.
- Kết quả normalize đúng ví dụ.

Lệnh người dùng tự chạy:
pytest tests/test_normalize_text.py -q
python - <<'PY'
from backend.knowledge_processing.normalize_text import normalize_article_no
print(normalize_article_no("Điều 04."))
print(normalize_article_no("điều 7a"))
PY
```

---

# P1.T3 — Hugging Face generic loader

```text
Task ID: P1.T3

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/02_data_loading_huggingface.md
- skills/11_code_quality_testing.md

Chỉ triển khai P1.T3: Hugging Face generic loader.

Tạo/sửa:
- backend/knowledge_processing/hf_loader.py

Functions:
- load_hf_dataset_to_polars(dataset_name: str, config_name: str | None, split: str = "train") -> pl.DataFrame
- save_parquet(df: pl.DataFrame, output_path: str | Path) -> None

Yêu cầu:
- Dùng datasets.load_dataset.
- Convert sang Polars DataFrame.
- Không load dataset ở import-time.
- Có error message rõ nếu load fail.
- Không chạy lệnh.

Acceptance Criteria:
- Function import được.
- Có thể load HF dataset khi người dùng tự chạy.
- save_parquet tạo parent directory nếu chưa tồn tại.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.knowledge_processing.hf_loader import load_hf_dataset_to_polars
df = load_hf_dataset_to_polars("tmquan/phapdien-moj-gov-vn", "articles", "train")
print(df.shape)
print(df.columns[:5])
PY
```

---

# P1.T4 — Load testset

```text
Task ID: P1.T4

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/02_data_loading_huggingface.md
- skills/03_legal_normalization.md
- skills/11_code_quality_testing.md

Chỉ triển khai P1.T4: load testset.

Tạo/sửa:
- backend/schema/question.py nếu chưa có
- backend/knowledge_processing/load_testset.py
- scripts/01_load_testset.py
- tests/test_load_testset.py nếu phù hợp

Input:
- data/raw/R2AIStage1DATA.json

Output:
- data/processed/test_questions.parquet

Yêu cầu:
- Validate JSON là list.
- Mỗi row phải có id và question.
- id convert được sang int.
- question không rỗng sau normalize.
- Không duplicate id.
- Raise lỗi rõ nếu format sai.
- Script chỉ gọi backend function.
- Không chạy lệnh.

Acceptance Criteria:
- Tạo được parquet khi người dùng chạy script.
- Output columns gồm id, question.
- Có validation duplicate id.
- Có test cho loader với fixture nhỏ nếu phù hợp.

Lệnh người dùng tự chạy:
python scripts/01_load_testset.py
python - <<'PY'
import polars as pl
df = pl.read_parquet("data/processed/test_questions.parquet")
print(df.shape)
print(df.head(3))
print(df["id"].n_unique())
PY
```

---

# P1.T5 — Load phapdien

```text
Task ID: P1.T5

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/02_data_loading_huggingface.md
- skills/04_canonical_article_registry.md
- skills/11_code_quality_testing.md

Chỉ triển khai P1.T5: load phapdien.

Tạo/sửa:
- backend/schema/phapdien_article.py nếu chưa có
- backend/knowledge_processing/load_phapdien.py

Dataset:
- tmquan/phapdien-moj-gov-vn
- config: articles
- split: train

Output:
- data/processed/phapdien_articles.parquet

Columns cần có:
- phapdien_id
- topic_title
- subject_title
- chapter_title
- article_title
- content_text
- source_note_text
- related_note_text
- source_url
- source_links_json

Yêu cầu:
- Dùng hf_loader.
- Normalize text fields.
- Serialize source_links thành JSON string.
- Không dùng article_title làm official relevant_articles.
- Không chạy lệnh.

Acceptance Criteria:
- Tạo được parquet khi người dùng gọi function.
- content_text được giữ.
- source_note_text được giữ.
- source_links_json parse được về JSON nếu có dữ liệu.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.knowledge_processing.load_phapdien import load_phapdien_articles
df = load_phapdien_articles("data/processed/phapdien_articles.parquet")
print(df.shape)
print(df.columns)
print(df.select("article_title", "content_text").head(3))
PY
```

---

# P1.T6 — Load anle

```text
Task ID: P1.T6

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/02_data_loading_huggingface.md
- skills/11_code_quality_testing.md

Chỉ triển khai P1.T6: load anle.

Tạo/sửa:
- backend/schema/anle_unit.py nếu chưa có
- backend/knowledge_processing/load_anle.py

Dataset:
- tmquan/anle-toaan-gov-vn
- config: sentences
- split: train

Output:
- data/processed/anle_units.parquet

Yêu cầu:
- Load sentence/paragraph-level units.
- Tạo unit_id ổn định.
- Text không rỗng.
- Không dùng embedding có sẵn từ dataset.
- anle chỉ là auxiliary source.
- Không chạy lệnh.

Acceptance Criteria:
- Tạo được anle_units.parquet khi người dùng gọi function.
- unit_id unique.
- Có text.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.knowledge_processing.load_anle import load_anle_sentences
df = load_anle_sentences("data/processed/anle_units.parquet")
print(df.shape)
print(df.columns)
print(df.head(3))
PY
```

---

# P1.T7 — Load VBPL documents

```text
Task ID: P1.T7

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/02_data_loading_huggingface.md
- skills/03_legal_normalization.md
- skills/04_canonical_article_registry.md
- skills/11_code_quality_testing.md

Chỉ triển khai P1.T7: load VBPL documents.

Tạo/sửa:
- backend/schema/legal_document.py nếu chưa có
- backend/knowledge_processing/load_vbpl.py

Dataset:
- tmquan/vbpl-vn

Output:
- data/processed/legal_documents.parquet

Columns:
- doc_id
- law_id
- law_type
- law_title
- normalized_title
- source_url
- markdown
- issue_date
- effective_date
- status
- legal_area

Yêu cầu:
- Load document-level rows.
- Normalize title.
- Giữ markdown/body text để extract articles ở task sau.
- Log rows thiếu law_id hoặc markdown.
- Không extract articles trong task này.
- Không chạy lệnh.

Acceptance Criteria:
- Tạo được legal_documents.parquet.
- Có markdown.
- Có normalized_title.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.knowledge_processing.load_vbpl import load_vbpl_documents
df = load_vbpl_documents("data/processed/legal_documents.parquet")
print(df.shape)
print(df.columns)
print(df.select("law_id", "normalized_title").head(5))
PY
```

---

# P1.T8 — Extract legal articles

```text
Task ID: P1.T8

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/03_legal_normalization.md
- skills/04_canonical_article_registry.md
- skills/11_code_quality_testing.md

Chỉ triển khai P1.T8: extract legal articles.

Tạo/sửa:
- backend/knowledge_processing/extract_articles.py
- tests/test_extract_articles.py nếu phù hợp

Input:
- data/processed/legal_documents.parquet

Output:
- data/processed/legal_articles.parquet

Yêu cầu:
- Tách Điều luật từ markdown/body.
- article_no format: Điều X.
- article_id format: law_id|law_title|article_no.
- Bỏ qua hoặc log article thiếu law_id/law_title/article_no/article_text.
- Log documents không extract được Điều nào.
- Không chạy lệnh.

Acceptance Criteria:
- Tạo được legal_articles.parquet.
- article_id unique.
- Không có row thiếu field bắt buộc.
- Có test regex cơ bản.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.knowledge_processing.extract_articles import extract_articles_from_vbpl
df = extract_articles_from_vbpl(
    "data/processed/legal_documents.parquet",
    "data/processed/legal_articles.parquet"
)
print(df.shape)
print(df.select("article_id", "article_no").head(5))
print("unique article_id:", df["article_id"].n_unique())
PY
```

---

# P1.T9 — Map phapdien to VBPL

```text
Task ID: P1.T9

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/04_canonical_article_registry.md
- skills/11_code_quality_testing.md

Chỉ triển khai P1.T9: map phapdien sang canonical legal_articles.

Tạo/sửa:
- backend/knowledge_processing/map_phapdien_to_vbpl.py

Input:
- data/processed/phapdien_articles.parquet
- data/processed/legal_articles.parquet

Output:
- data/processed/phapdien_to_vbpl_map.parquet

Mapping strategy:
1. Parse Điều X từ source_note_text.
2. Match candidate LegalArticle theo article_no.
3. Fuzzy match giữa source_note_text và law_title.
4. Fuzzy/content overlap giữa phapdien content_text và legal article_text.
5. Lưu mapping_score và mapping_method.
6. Chỉ giữ mapping vượt threshold.
7. Log mapping confidence thấp.

Yêu cầu:
- Không dùng phapdien article_title làm citation chính thức.
- Không chạy lệnh.

Acceptance Criteria:
- Có phapdien_id.
- Có legal_article_id.
- Có law_id/law_title/article_no.
- Có mapping_score/mapping_method.
- Có log low confidence mapping.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.knowledge_processing.map_phapdien_to_vbpl import build_phapdien_to_vbpl_map
df = build_phapdien_to_vbpl_map(
    "data/processed/phapdien_articles.parquet",
    "data/processed/legal_articles.parquet",
    "data/processed/phapdien_to_vbpl_map.parquet"
)
print(df.shape)
print(df.head(5))
PY
```

---

# P1.T10 — Build corpus orchestration

```text
Task ID: P1.T10

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/02_data_loading_huggingface.md
- skills/03_legal_normalization.md
- skills/04_canonical_article_registry.md
- skills/11_code_quality_testing.md

Chỉ triển khai P1.T10: orchestration cho Phase 1.

Tạo/sửa:
- backend/knowledge_processing/build_corpus.py
- scripts/01_build_corpus.py

Yêu cầu:
- build_corpus.py gọi các task Phase 1 theo thứ tự:
  1. load testset
  2. load phapdien
  3. load anle
  4. load vbpl
  5. extract legal articles
  6. map phapdien to vbpl
- scripts/01_build_corpus.py chỉ là entrypoint.
- Có logging từng step.
- Có option skip_existing nếu phù hợp.
- Không chạy lệnh.

Acceptance Criteria:
- Script tạo đủ 6 parquet outputs khi người dùng chạy.
- Script không chứa business logic lớn.
- Có lỗi rõ nếu thiếu input file.

Lệnh người dùng tự chạy:
python scripts/01_build_corpus.py
ls -lh data/processed
```

---

# P2.T1 — Infrastructure clients

```text
Task ID: P2.T1

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/05_embedding_vnlegal_lal.md
- skills/06_hybrid_retrieval.md
- skills/11_code_quality_testing.md

Chỉ triển khai P2.T1: infrastructure clients.

Tạo/sửa:
- backend/infrastructure/search_engine/opensearch_client.py
- backend/infrastructure/vector_store/qdrant_client.py
- backend/infrastructure/database/duckdb_client.py

Yêu cầu:
- OpenSearch client có health_check().
- Qdrant client có health_check().
- DuckDB client đọc parquet được.
- Không connect hoặc tạo index ở import-time.
- Không chạy lệnh.

Acceptance Criteria:
- Import clients không lỗi.
- Có config-based host/port.
- Có error handling cơ bản.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.infrastructure.database.duckdb_client import DuckDBClient
db = DuckDBClient()
print("duckdb ok")
PY
```

---

# P2.T2 — vnlegal-lal embedding wrapper

```text
Task ID: P2.T2

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/05_embedding_vnlegal_lal.md
- skills/11_code_quality_testing.md

Chỉ triển khai P2.T2: embedding wrapper.

Tạo/sửa:
- backend/infrastructure/embedding_models/vnlegal_lal.py

Yêu cầu:
- Class VNLegalLALEmbedder.
- encode_query() có instruction prefix:
  Instruct: Given a Vietnamese legal question, retrieve relevant legal passages that answer the question
  Query:
- encode_documents() không có query prefix.
- Output vector normalized.
- Có batching.
- Không load model ở import-time nếu có thể tránh.
- Không chạy lệnh.

Acceptance Criteria:
- Import class không lỗi.
- encode_query trả vector.
- encode_documents trả list vector.
- Nếu model load đúng, vector dim = 1024.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.infrastructure.embedding_models.vnlegal_lal import VNLegalLALEmbedder
m = VNLegalLALEmbedder()
v = m.encode_query("Doanh nghiệp nhỏ và vừa là gì?")
print(len(v), v[:5])
PY
```

---

# P2.T3 — Build BM25 indexes

```text
Task ID: P2.T3

Chỉ triển khai P2.T3: build BM25 indexes.

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/06_hybrid_retrieval.md
- skills/11_code_quality_testing.md

Tạo/sửa:
- backend/indexing/build_bm25_index.py

Input:
- data/processed/legal_articles.parquet
- data/processed/phapdien_articles.parquet
- data/processed/anle_units.parquet

Indexes:
- legal_articles_bm25
- phapdien_articles_bm25
- anle_units_bm25

Yêu cầu:
- Có recreate flag.
- Có mapping fields hợp lý.
- Index legal article fields: law_title, article_no, article_title, article_text, domain.
- Không chạy lệnh.

Acceptance Criteria:
- Function build_all_bm25_indexes(recreate: bool) tồn tại.
- Có thể build từng index riêng.
- Payload giữ canonical article_id với legal_articles.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.indexing.build_bm25_index import build_all_bm25_indexes
build_all_bm25_indexes(recreate=True)
print("bm25 indexes built")
PY
```

---

# P2.T4 — Build vector indexes

```text
Task ID: P2.T4

Chỉ triển khai P2.T4: build vector indexes.

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/05_embedding_vnlegal_lal.md
- skills/06_hybrid_retrieval.md
- skills/11_code_quality_testing.md

Tạo/sửa:
- backend/indexing/build_vector_index.py

Input:
- data/processed/legal_articles.parquet
- data/processed/phapdien_articles.parquet
- data/processed/anle_units.parquet

Qdrant collections:
- legal_articles_dense
- phapdien_articles_dense
- anle_units_dense

Yêu cầu:
- Dùng VNLegalLALEmbedder.
- Text format cho legal article:
  Tên văn bản: {law_title}
  Điều: {article_no}
  Tiêu đề điều: {article_title}
  Nội dung:
  {article_text}
- Payload giữ article_id/phapdien_id/unit_id.
- Có batching.
- Có recreate flag.
- Không chạy lệnh.

Acceptance Criteria:
- Function build_all_vector_indexes(recreate: bool) tồn tại.
- Tạo đúng collection names.
- Không trộn embedding model khác.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.indexing.build_vector_index import build_all_vector_indexes
build_all_vector_indexes(recreate=True)
print("vector indexes built")
PY
```

---

# P2.T5 — Build exact index

```text
Task ID: P2.T5

Chỉ triển khai P2.T5: build exact index.

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/06_hybrid_retrieval.md
- skills/11_code_quality_testing.md

Tạo/sửa:
- backend/indexing/build_exact_index.py

Input:
- data/processed/legal_articles.parquet

Output:
- data/processed/exact_index.json hoặc exact_index.parquet

Support exact lookup:
- law_id
- article_no
- tài khoản kế toán
- deadline numbers
- sanction keywords

Yêu cầu:
- Exact index load nhanh.
- Có format documented.
- Không chạy lệnh.

Acceptance Criteria:
- build_exact_index() tồn tại.
- Output file được tạo khi người dùng chạy.
- Có lookup key cho Điều X và law_id.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.indexing.build_exact_index import build_exact_index
idx = build_exact_index("data/processed/legal_articles.parquet", "data/processed/exact_index.json")
print(idx.keys())
PY
```

---

# P2.T6 — Build indexes orchestration

```text
Task ID: P2.T6

Chỉ triển khai P2.T6: orchestration cho indexing.

Tạo/sửa:
- scripts/02_build_indexes.py

Yêu cầu:
- Gọi BM25 builder.
- Gọi vector builder.
- Gọi exact index builder.
- Có logging từng step.
- Script không chứa business logic lớn.
- Không chạy lệnh.

Acceptance Criteria:
- Người dùng chạy script sẽ build toàn bộ indexes.
- Có flag/config recreate nếu phù hợp.

Lệnh người dùng tự chạy:
python scripts/02_build_indexes.py
```

---

# P3.T1 — Domain router

```text
Task ID: P3.T1

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/07_query_analysis.md
- skills/11_code_quality_testing.md

Chỉ triển khai P3.T1: domain router.

Tạo/sửa:
- backend/query_analysis/domain_router.py
- tests/test_domain_router.py

Domains:
- sme_support
- tax_invoice
- labor_bhxh
- accounting
- ip_consumer_data
- business_registration
- commerce_contract
- credit_guarantee
- environment
- other

Yêu cầu:
- Rule-based trước.
- Return domain + confidence + matched_keywords nếu phù hợp.
- Không hard-filter retrieval.
- Không chạy lệnh.

Acceptance Criteria:
- classify_domain(question) chạy được.
- Có fallback other.
- Có pytest.

Lệnh người dùng tự chạy:
pytest tests/test_domain_router.py -q
```

---

# P3.T2 — Answer type classifier

```text
Task ID: P3.T2

Chỉ triển khai P3.T2: answer type classifier.

Tạo/sửa:
- backend/query_analysis/answer_type_classifier.py
- tests/test_answer_type_classifier.py

Answer types:
- deadline
- amount
- sanction
- procedure
- dossier
- conditions
- obligations
- yes_no
- accounting_account
- definition
- multi_part

Yêu cầu:
- Rule-based heuristic.
- Return answer_type + confidence.
- Không chạy lệnh.

Acceptance Criteria:
- classify_answer_type(question) chạy được.
- Có pytest cho các type chính.
- Có fallback general/definition.

Lệnh người dùng tự chạy:
pytest tests/test_answer_type_classifier.py -q
```

---

# P3.T3 — Complexity detector

```text
Task ID: P3.T3

Chỉ triển khai P3.T3: complexity detector.

Tạo/sửa:
- backend/query_analysis/complexity_detector.py
- tests/test_complexity_detector.py

Detect:
- single_hop
- multi_hop

Multi-hop cues:
- vừa
- đồng thời
- sau đó
- trong khi
- nhiều domain signals

Yêu cầu:
- Return complexity + score/reason.
- Không chạy lệnh.

Acceptance Criteria:
- Detect được single_hop.
- Detect được multi_hop.
- Có pytest.

Lệnh người dùng tự chạy:
pytest tests/test_complexity_detector.py -q
```

---

# P3.T4 — Legal entity extractor

```text
Task ID: P3.T4

Chỉ triển khai P3.T4: legal entity extractor.

Tạo/sửa:
- backend/query_analysis/legal_entity_extractor.py
- tests/test_legal_entity_extractor.py

Extract:
- Điều X
- Luật/Nghị định/Thông tư nếu có
- tài khoản kế toán
- ngày/tháng/năm/thời hạn
- mức tiền phạt

Yêu cầu:
- Regex-based.
- Return structured dict.
- Không chạy lệnh.

Acceptance Criteria:
- Extract Điều X.
- Extract tài khoản kế toán.
- Extract thời hạn/mức tiền.
- Có pytest.

Lệnh người dùng tự chạy:
pytest tests/test_legal_entity_extractor.py -q
```

---

# P3.T5 — Query expander

```text
Task ID: P3.T5

Chỉ triển khai P3.T5: query expander.

Tạo/sửa:
- backend/query_analysis/query_expander.py
- tests/test_query_expander.py

Synonyms:
- DNNVV ↔ doanh nghiệp nhỏ và vừa
- hóa đơn đỏ ↔ hóa đơn GTGT
- cho nghỉ việc ↔ chấm dứt hợp đồng lao động
- trả nợ trước hạn ↔ tất toán sớm

Yêu cầu:
- Không làm mất query gốc.
- Return list expanded queries.
- Không expansion quá nhiều.
- Không chạy lệnh.

Acceptance Criteria:
- Expansion đúng các synonym chính.
- Có pytest.

Lệnh người dùng tự chạy:
pytest tests/test_query_expander.py -q
```

---

# P3.T6 — Analyze questions orchestration

```text
Task ID: P3.T6

Chỉ triển khai P3.T6: analyze questions orchestration.

Tạo/sửa:
- backend/query_analysis/analyze_question.py
- scripts/03_analyze_questions.py

Input:
- data/processed/test_questions.parquet

Output:
- data/processed/test_questions_analyzed.parquet

Yêu cầu:
- Mỗi câu có domain.
- Mỗi câu có answer_type.
- Mỗi câu có complexity.
- Có legal_entities_json.
- Có expanded_queries_json.
- Script không chứa business logic lớn.
- Không chạy lệnh.

Acceptance Criteria:
- Output có đủ 2.000 dòng nếu input đủ.
- Không mất id/question.
- JSON columns serialize được.

Lệnh người dùng tự chạy:
python scripts/03_analyze_questions.py
python - <<'PY'
import polars as pl
df = pl.read_parquet("data/processed/test_questions_analyzed.parquet")
print(df.shape)
print(df.select("id", "domain", "answer_type", "complexity").head(10))
PY
```

---

# P4.T1 — BM25 retriever

```text
Task ID: P4.T1

Chỉ triển khai P4.T1: BM25 retriever.

Tạo/sửa:
- backend/retrieval/bm25_retriever.py

Yêu cầu:
- search_legal_articles()
- search_phapdien()
- search_anle()
- Return normalized RetrievalHit objects/schema.
- Không expose raw OpenSearch response lên tầng trên.
- Không chạy lệnh.

Acceptance Criteria:
- Retriever import được.
- Có top_k parameter.
- Có score/source metadata.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.retrieval.bm25_retriever import BM25Retriever
r = BM25Retriever()
hits = r.search_legal_articles("doanh nghiệp nhỏ và vừa", top_k=5)
print(hits[:2])
PY
```

---

# P4.T2 — Dense retriever

```text
Task ID: P4.T2

Chỉ triển khai P4.T2: dense retriever.

Tạo/sửa:
- backend/retrieval/dense_retriever.py

Yêu cầu:
- search_legal_articles_dense()
- search_phapdien_dense()
- search_anle_dense()
- Dùng VNLegalLALEmbedder.encode_query().
- Return normalized RetrievalHit objects.
- Không chạy lệnh.

Acceptance Criteria:
- Retriever import được.
- Query dùng đúng prefix thông qua embedder.
- Có top_k parameter.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.retrieval.dense_retriever import DenseRetriever
r = DenseRetriever()
hits = r.search_legal_articles_dense("doanh nghiệp nhỏ và vừa", top_k=5)
print(hits[:2])
PY
```

---

# P4.T3 — Exact retriever

```text
Task ID: P4.T3

Chỉ triển khai P4.T3: exact retriever.

Tạo/sửa:
- backend/retrieval/exact_retriever.py

Yêu cầu:
- Load exact_index.
- Detect Điều X trong question.
- Detect mã văn bản nếu có.
- Detect tài khoản kế toán nếu có.
- Return canonical LegalArticle candidate IDs.
- Không chạy lệnh.

Acceptance Criteria:
- ExactRetriever import được.
- search() trả candidates.
- Không return phapdien/anle citation.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.retrieval.exact_retriever import ExactRetriever
r = ExactRetriever("data/processed/exact_index.json")
print(r.search("Theo Điều 4 Luật Hỗ trợ DNNVV thì sao?", top_k=5))
PY
```

---

# P4.T4 — Phapdien retriever + mapper

```text
Task ID: P4.T4

Chỉ triển khai P4.T4: phapdien retriever + mapper.

Tạo/sửa:
- backend/retrieval/phapdien_retriever.py

Yêu cầu:
- Search phapdien hits.
- Map phapdien_id sang legal_article_id bằng phapdien_to_vbpl_map.
- Output là canonical candidates.
- Có mapping_score.
- Không return phapdien article_title làm citation.
- Không chạy lệnh.

Acceptance Criteria:
- search_and_map() chạy được.
- Mapped output có legal_article_id.
- Có fallback khi không map được.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.retrieval.phapdien_retriever import PhapdienMappedRetriever
r = PhapdienMappedRetriever()
hits = r.search_and_map("hỗ trợ doanh nghiệp nhỏ và vừa", top_k=5)
print(hits[:2])
PY
```

---

# P4.T5 — RRF fusion

```text
Task ID: P4.T5

Chỉ triển khai P4.T5: RRF fusion.

Tạo/sửa:
- backend/retrieval/fusion.py
- tests/test_fusion.py

Yêu cầu:
- reciprocal_rank_fusion().
- merge_duplicate_articles().
- score_boost().
- Giữ source contribution.
- Không chạy lệnh.

Acceptance Criteria:
- RRF đúng công thức.
- Duplicate article_id được merge.
- Có pytest.

Lệnh người dùng tự chạy:
pytest tests/test_fusion.py -q
```

---

# P4.T6 — Article selector

```text
Task ID: P4.T6

Chỉ triển khai P4.T6: article selector.

Tạo/sửa:
- backend/retrieval/article_selector.py
- tests/test_article_selector.py

Dynamic max articles:
- deadline/accounting_account: 4
- yes_no: 5
- procedure/dossier: 7
- sanction: 6
- conditions/obligations: 8
- multi_hop: 12
- default: 7

Yêu cầu:
- Dedup.
- Respect max by answer_type/complexity.
- Có threshold nếu score available.
- Không chạy lệnh.

Acceptance Criteria:
- select_articles() chạy được.
- Có pytest cho dynamic max.
- Không chọn article duplicate.

Lệnh người dùng tự chạy:
pytest tests/test_article_selector.py -q
```

---

# P4.T7 — Hybrid retrieval orchestrator

```text
Task ID: P4.T7

Chỉ triển khai P4.T7: hybrid retrieval orchestrator.

Tạo/sửa:
- backend/retrieval/hybrid_retrieval.py

Pipeline:
1. Nhận question/analyzed question.
2. Gọi BM25 legal.
3. Gọi dense legal.
4. Gọi exact.
5. Gọi phapdien mapped.
6. RRF fusion.
7. Soft boost.
8. Article selection.
9. Return selected canonical LegalArticle IDs.

Không làm:
- Không dùng LLM.
- Không generate answer.
- Không cho phapdien/anle trực tiếp thành relevant_articles.
- Không chạy lệnh.

Acceptance Criteria:
- HybridLegalRetriever import được.
- retrieve() trả selected_articles.
- selected_articles là canonical article IDs.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.retrieval.hybrid_retrieval import HybridLegalRetriever
r = HybridLegalRetriever()
res = r.retrieve("Doanh nghiệp nhỏ và vừa được hỗ trợ những gì?")
print(res)
PY
```

---

# P4.T8 — Run retrieval script

```text
Task ID: P4.T8

Chỉ triển khai P4.T8: run retrieval script.

Tạo/sửa:
- scripts/04_run_retrieval.py

Input:
- data/processed/test_questions_analyzed.parquet

Output:
- data/outputs/retrieval_results.jsonl

Yêu cầu:
- Script đọc analyzed questions.
- Gọi HybridLegalRetriever.
- Ghi JSONL từng câu.
- Mỗi row có id, question, selected_articles.
- Có logging tiến độ.
- Script không chứa business logic lớn.
- Không chạy lệnh.

Acceptance Criteria:
- retrieval_results.jsonl tạo được khi người dùng chạy.
- selected_articles chỉ chứa canonical article IDs.

Lệnh người dùng tự chạy:
python scripts/04_run_retrieval.py
head -n 3 data/outputs/retrieval_results.jsonl
```

---

# P5.T1 — LLM client

```text
Task ID: P5.T1

Chỉ triển khai P5.T1: LLM client.

Tạo/sửa:
- backend/infrastructure/gen_llm_models/vllm_client.py
- backend/infrastructure/gen_llm_models/qwen_client.py

Yêu cầu:
- Configurable endpoint/model.
- temperature default = 0.
- Timeout/retry cơ bản.
- Không gọi LLM ở import-time.
- Không chạy lệnh.

Acceptance Criteria:
- Client import được.
- Có generate() hoặc chat() method.
- Có config cho model name.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.infrastructure.gen_llm_models.vllm_client import VLLMClient
print("client import ok")
PY
```

---

# P5.T2 — Answer templates + prompt

```text
Task ID: P5.T2

Chỉ triển khai P5.T2: answer templates + prompt.

Tạo/sửa:
- backend/qa/answer_templates.py
- backend/prompts/legal_qa_prompt.txt

Yêu cầu:
- Có template general.
- Có template deadline.
- Có template sanction.
- Có template procedure/dossier.
- Có template yes_no.
- Prompt yêu cầu chỉ dùng selected_articles.
- Prompt yêu cầu nhắc Điều X.
- Không chạy lệnh.

Acceptance Criteria:
- build_answer_prompt() chạy được.
- Prompt không yêu cầu LLM tự sinh relevant_articles.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.qa.answer_templates import build_answer_prompt
print(build_answer_prompt(question="Câu hỏi test", articles=[], answer_type="general")[:500])
PY
```

---

# P5.T3 — Answer generator

```text
Task ID: P5.T3

Chỉ triển khai P5.T3: answer generator.

Tạo/sửa:
- backend/qa/answer_generator.py

Yêu cầu:
- Input gồm question, selected_articles, answer_type.
- Build context từ selected_articles.
- Gọi LLM client.
- Không sinh relevant_docs/relevant_articles.
- Có fallback nếu selected_articles rỗng.
- Không chạy lệnh.

Acceptance Criteria:
- AnswerGenerator import được.
- Có generate_answer() method.
- Không phụ thuộc trực tiếp vào submission builder.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.qa.answer_generator import AnswerGenerator
print("answer generator import ok")
PY
```

---

# P5.T4 — Citation postprocess

```text
Task ID: P5.T4

Chỉ triển khai P5.T4: citation postprocess.

Tạo/sửa:
- backend/qa/citation_postprocess.py
- tests/test_citation_postprocess.py

Yêu cầu:
- Kiểm tra answer có nhắc Điều X đã chọn.
- Append "Căn cứ pháp lý" nếu thiếu.
- Không thêm Điều ngoài selected_articles.
- Không chạy lệnh.

Acceptance Criteria:
- Có pytest.
- Không làm mất nội dung answer gốc.
- Không bịa citation.

Lệnh người dùng tự chạy:
pytest tests/test_citation_postprocess.py -q
```

---

# P5.T5 — Submission builder

```text
Task ID: P5.T5

Chỉ triển khai P5.T5: submission builder.

Tạo/sửa:
- backend/submission/build_results.py
- backend/submission/validate_results.py
- backend/submission/make_zip.py
- tests/test_submission_validation.py

Yêu cầu:
- results.json là JSON list.
- Mỗi item có id, question, answer, relevant_docs, relevant_articles.
- relevant_docs derive từ selected_articles.
- relevant_articles derive từ canonical LegalArticle.
- Validate duplicate id.
- Validate format relevant_docs.
- Validate format relevant_articles.
- Zip chỉ chứa results.json ở root.
- Không chạy lệnh.

Acceptance Criteria:
- Có validator.
- Có make_zip.
- Có pytest validation.
- LLM không liên quan đến citation generation.

Lệnh người dùng tự chạy:
pytest tests/test_submission_validation.py -q
```

---

# P5.T6 — QA + submission scripts

```text
Task ID: P5.T6

Chỉ triển khai P5.T6: QA + submission scripts.

Tạo/sửa:
- scripts/05_generate_answers.py
- scripts/06_build_submission.py
- scripts/07_validate_submission.py

Yêu cầu:
- generate_answers đọc retrieval_results.jsonl.
- build_submission tạo results.json.
- validate_submission kiểm tra schema/format.
- Scripts không chứa business logic lớn.
- Không chạy lệnh.

Acceptance Criteria:
- Tạo data/outputs/answers.jsonl.
- Tạo data/outputs/results.json.
- Tạo data/outputs/submission.zip.
- Validate pass khi người dùng chạy.

Lệnh người dùng tự chạy:
python scripts/05_generate_answers.py
python scripts/06_build_submission.py
python scripts/07_validate_submission.py
ls -lh data/outputs/results.json data/outputs/submission.zip
```

---

# P6.T1 — Metrics

```text
Task ID: P6.T1

Chỉ triển khai P6.T1: metrics.

Tạo/sửa:
- backend/evaluation/metrics.py
- tests/test_metrics.py

Functions:
- precision()
- recall()
- f2_score()
- hit_at_k()
- mrr()

Yêu cầu:
- Handle empty predictions/gold.
- Có pytest.
- Không chạy lệnh.

Acceptance Criteria:
- Metrics đúng với case nhỏ.
- Không phụ thuộc vào retrieval pipeline.

Lệnh người dùng tự chạy:
pytest tests/test_metrics.py -q
```

---

# P6.T2 — Error analysis report

```text
Task ID: P6.T2

Chỉ triển khai P6.T2: error analysis report.

Tạo/sửa:
- backend/evaluation/error_analysis.py

Input:
- data/outputs/retrieval_results.jsonl
- data/outputs/results.json
- optional pseudo labels

Output:
- data/outputs/error_analysis/low_confidence_questions.csv
- data/outputs/error_analysis/retrieval_debug_report.csv

Error categories:
- missing_corpus
- wrong_domain
- wrong_article
- right_article_low_rank
- phapdien_mapping_error
- too_many_articles
- too_few_articles
- answer_missing_citation
- multi_hop_missing_branch
- invalid_submission_format

Yêu cầu:
- Không cần labels vẫn tạo report mô tả được.
- Không chạy lệnh.

Acceptance Criteria:
- build_error_analysis_report() import được.
- Output folder tự tạo nếu thiếu.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.evaluation.error_analysis import build_error_analysis_report
print("error analysis import ok")
PY
```

---

# P7.T1 — Reranker interface

```text
Task ID: P7.T1

Chỉ triển khai P7.T1: reranker interface.

Tạo/sửa:
- backend/retrieval/reranker.py

Yêu cầu:
- Có BaseReranker interface.
- Có NoOpReranker fallback.
- Không phá baseline retrieval.
- Không chạy lệnh.

Acceptance Criteria:
- NoOpReranker giữ nguyên order candidates.
- Có type hints.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.retrieval.reranker import NoOpReranker
print(NoOpReranker().rerank("q", []))
PY
```

---

# P7.T2 — LLM verifier

```text
Task ID: P7.T2

Chỉ triển khai P7.T2: LLM verifier.

Tạo/sửa:
- backend/retrieval/llm_verifier.py
- backend/prompts/verifier_prompt.txt

Verifier JSON:
{
  "relevant": true,
  "confidence": 0.86,
  "reason": "..."
}

Yêu cầu:
- Parse JSON output.
- Có fallback khi JSON lỗi.
- Chỉ dùng khi config bật.
- Không chạy lệnh.

Acceptance Criteria:
- LLMVerifier import được.
- Có verify() method.
- Không tự gọi LLM ở import-time.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.retrieval.llm_verifier import LLMVerifier
print("verifier import ok")
PY
```

---

# P8.T1 — Neo4j client

```text
Task ID: P8.T1

Chỉ triển khai P8.T1: Neo4j client.

Tạo/sửa:
- backend/infrastructure/graph_store/neo4j_client.py

Yêu cầu:
- health_check().
- run_read_query().
- run_write_query().
- Không connect ở import-time.
- Không chạy lệnh.

Acceptance Criteria:
- Client import được.
- Config host/user/pass từ settings/env.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.infrastructure.graph_store.neo4j_client import Neo4jClient
print("neo4j client import ok")
PY
```

---

# P8.T2 — Build graph index

```text
Task ID: P8.T2

Chỉ triển khai P8.T2: build graph index.

Tạo/sửa:
- backend/indexing/build_graph_index.py

Nodes:
- Law
- Article
- PhapdienArticle
- AnleCase
- Domain
- Concept

Relationships:
- Law - HAS_ARTICLE -> Article
- PhapdienArticle - DERIVED_FROM -> Article
- Article - RELATED_TO -> Article
- Article - BELONGS_TO_DOMAIN -> Domain
- AnleCase - APPLIES_ARTICLE -> Article

Yêu cầu:
- Có constraints Cypher.
- Có batch insert.
- Không chạy lệnh.

Acceptance Criteria:
- build_graph_index import được.
- Có function tạo constraints.
- Có function build nodes/relationships.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.indexing.build_graph_index import build_graph_index
print("graph builder import ok")
PY
```

---

# P8.T3 — Graph expander

```text
Task ID: P8.T3

Chỉ triển khai P8.T3: graph expander.

Tạo/sửa:
- backend/retrieval/graph_expander.py

Yêu cầu:
- Input candidate_article_ids.
- Return neighbor_article_ids + graph_boost_scores.
- Không add neighbor mù quáng.
- Có max_neighbors config.
- Không chạy lệnh.

Acceptance Criteria:
- GraphExpander import được.
- Có expand() method.
- Có fallback khi Neo4j unavailable.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.retrieval.graph_expander import GraphExpander
print("graph expander import ok")
PY
```

---

# P9.T1 — Reranker training data builder

```text
Task ID: P9.T1

Chỉ triển khai P9.T1: chuẩn bị data fine-tuning reranker.

Tạo/sửa:
- backend/evaluation/build_reranker_training_data.py

Input:
- retrieval logs
- low confidence report
- pseudo labels nếu có
- manual annotations nếu có

Output format:
{
  "query": "...",
  "positive_article_id": "...",
  "hard_negative_article_ids": [...]
}

Yêu cầu:
- Hard negatives từ top retrieved sai.
- Same law wrong article.
- Same domain wrong rule.
- Validate article_id tồn tại trong legal_articles.
- Không fine-tune model.
- Không chạy lệnh.

Acceptance Criteria:
- Function import được.
- Output JSONL/parquet training data.
- Không gọi training framework.

Lệnh người dùng tự chạy:
python - <<'PY'
from backend.evaluation.build_reranker_training_data import build_reranker_training_data
print("training data builder import ok")
PY
```

---

# U1 — End-to-end baseline runner

```text
Task ID: U1

Chỉ triển khai U1: end-to-end baseline runner.

Tạo/sửa:
- scripts/run_phase_1_to_5_baseline.py

Yêu cầu:
Script gọi lần lượt:
1. build corpus
2. build indexes
3. analyze questions
4. run retrieval
5. generate answers
6. build submission
7. validate submission

Rules:
- Có logging start/end mỗi step.
- Stop on failure.
- Không duplicate business logic.
- Không chạy script sau khi tạo.

Acceptance Criteria:
- Script import/call các scripts hoặc backend modules hiện có.
- Có main guard.
- Có command rõ cho người dùng tự chạy.

Lệnh người dùng tự chạy:
python scripts/run_phase_1_to_5_baseline.py
```

---

# U2 — Debug retrieval for one question

```text
Task ID: U2

Chỉ triển khai U2: debug retrieval cho một câu hỏi.

Tạo/sửa:
- scripts/debug_retrieval_for_question.py

Usage:
python scripts/debug_retrieval_for_question.py --id 123

Script cần in:
- question
- domain
- answer_type
- complexity
- BM25 legal hits
- dense legal hits
- exact hits
- phapdien hits
- mapped phapdien articles
- RRF merged candidates
- selected final articles

Không generate answer.
Không chạy lệnh.

Acceptance Criteria:
- Có argparse --id.
- Không cần LLM.
- Có output dễ đọc để debug.

Lệnh người dùng tự chạy:
python scripts/debug_retrieval_for_question.py --id 1
```

---

# FIX.TASK — Prompt sửa lỗi task cụ thể

```text
Task ID: FIX.TASK

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skill file liên quan đến module lỗi

Tôi đang ở task:
[DÁN TASK ID]

Tôi đã tự chạy command:
[DÁN COMMAND]

Lỗi nhận được:
[DÁN ERROR LOG]

Hãy:
1. Xác định root cause.
2. Sửa tối thiểu phần code cần thiết.
3. Không rewrite module không liên quan.
4. Không mở rộng scope sang task khác.
5. Giữ nguyên architecture project.
6. Thêm regression test nếu phù hợp.
7. Không chạy lệnh thay tôi.
8. Trả lại lệnh để tôi tự chạy kiểm tra lại.

Output cần có:
- Root cause.
- Files changed.
- Fix summary.
- Acceptance Criteria được kiểm tra lại.
- Commands tôi cần chạy.
```

---

# TEST.TASK — Prompt yêu cầu viết test cho task

```text
Task ID: TEST.TASK

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/11_code_quality_testing.md

Tôi muốn bổ sung test cho:
[DÁN MODULE/FUNCTION/TASK ID]

Yêu cầu:
- Dùng pytest.
- Bao phủ normal cases.
- Bao phủ edge cases.
- Bao phủ invalid input.
- Có ví dụ text pháp luật tiếng Việt nếu phù hợp.
- Không đổi production code trừ khi cần để code dễ test.
- Không chạy lệnh.

Output:
- Files changed.
- Test cases đã thêm.
- Lệnh tôi tự chạy:
  pytest [TEST FILE] -q
```

---

# REFACTOR.TASK — Prompt refactor module

```text
Task ID: REFACTOR.TASK

Hãy đọc:
- context.md
- legal_rag_phase_plan_v3.md
- skills/11_code_quality_testing.md

Refactor module:
[DÁN MODULE PATH]

Mục tiêu:
- Code dễ đọc hơn.
- Có type hints.
- Tách function quá dài.
- Giữ nguyên behavior.
- Thêm comment tiếng Việt cho logic phức tạp.
- Không đổi public interface nếu không cần.
- Không chạy lệnh.

Output:
- Files changed.
- Refactor summary.
- Risks nếu có.
- Lệnh tôi tự chạy để kiểm tra:
  pytest [RELATED TESTS] -q
```

---

# REVIEW.TASK — Prompt review code sau khi Codex làm xong

```text
Task ID: REVIEW.TASK

Hãy review thay đổi của task:
[DÁN TASK ID]

Yêu cầu review:
1. Có vượt scope task không?
2. Có vi phạm nguyên tắc LLM không tự sinh relevant_articles không?
3. Có hard-code path không?
4. Có script chứa business logic quá nhiều không?
5. Có AC nào chưa đáp ứng không?
6. Có test/validation command rõ chưa?
7. Có chỗ nào dễ lỗi khi chạy trên dữ liệu thật không?

Không sửa code vội.
Chỉ trả về review findings và đề xuất fix theo mức:
- must fix
- should fix
- nice to have
```
