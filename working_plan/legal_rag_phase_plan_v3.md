# Legal Graph RAG — Phase & Task Plan v3.1

> File liên quan trực tiếp: `codex_task_prompts_vi_v3.md`  
> Bản cập nhật: Phase 2 dùng `legal_article_chunks.parquet` cho BM25/vector; Neo4j ở Phase 8.  
> Cách dùng: mở file prompt, chọn đúng `Task ID` tương ứng trong plan này, copy prompt cho Codex.  
> Quy tắc vận hành: **Codex chỉ sửa code và đề xuất lệnh kiểm thử; người dùng là người chạy lệnh.**

---

## 0. Nguyên tắc kiểm soát Codex

### 0.1. Quy tắc bắt buộc

1. Codex phải đọc `context.md`, `legal_rag_phase_plan_v3.md` và các skill liên quan trước khi code.
2. Codex chỉ được triển khai đúng `Task ID` được giao.
3. Codex không được tự mở rộng sang phase/task khác.
4. Codex không được chạy lệnh build/test/index/generate trên máy người dùng.
5. Codex phải liệt kê rõ các lệnh để **người dùng tự chạy**.
6. Mỗi task phải có:
   - Deliverables
   - Acceptance Criteria
   - Test/Validation Commands
   - Expected Outputs
   - Rollback/Debug note nếu phù hợp
7. Scripts chỉ là entrypoint mỏng; business logic phải nằm trong `backend/`.
8. Không hard-code path; dùng config.
9. LLM không được tự sinh `relevant_docs` hoặc `relevant_articles`.
10. `relevant_docs` và `relevant_articles` chỉ được sinh từ canonical `legal_articles.parquet`.

### 0.2. Cấu trúc làm việc với Codex

Với mỗi task:

```text
1. Người dùng chọn Task ID trong plan.
2. Người dùng copy prompt tương ứng từ codex_task_prompts_vi_v3.md.
3. Codex sửa/tạo code.
4. Codex trả lại:
   - File đã thay đổi
   - Tóm tắt thay đổi
   - Lệnh người dùng cần chạy
   - Acceptance Criteria checklist
5. Người dùng tự chạy lệnh.
6. Nếu lỗi, dùng prompt "FIX.TASK" trong codex_task_prompts_vi_v3.md.
```

### 0.3. Quy trình báo cáo bắt buộc trước/sau khi sửa code

## Quy trình báo cáo bắt buộc trước/sau khi sửa code

### Trước khi sửa code

Trước khi sửa bất kỳ file nào, Codex phải trình bày ngắn gọn:

```text
Scope bạn hiểu:
- ...

Files dự kiến sửa:
- ...

Test command sẽ chạy / đề xuất người dùng chạy:
- ...
```

Sau khi trình bày phần này, Codex phải **dừng lại và chờ người dùng xác nhận** trước khi sửa code, trừ khi người dùng đã ghi rõ: `triển khai luôn`.

### Sau khi hoàn thành

Sau khi sửa code xong, Codex phải báo cáo:

```text
Files changed:
- ...

Logic thay đổi:
- ...

Acceptance Criteria đã đạt/chưa đạt:
- [x] ...
- [ ] ...

Test result:
- Tôi không tự chạy lệnh. Người dùng cần chạy:
  ...
- Nếu người dùng đã cung cấp log test, tóm tắt kết quả tại đây.

Risk còn lại:
- ...
```

Quy tắc quan trọng: **Codex không tự chạy lệnh thay người dùng**. Codex chỉ đề xuất lệnh kiểm thử/validation để người dùng tự chạy.

---

## 1. Pipeline tổng thể

```text
R2AIStage1DATA.json
↓
Phase 1: Data loading + canonical corpus
↓
Phase 2: Indexing
  - OpenSearch / BM25
  - Qdrant / dense vector
  - Exact index
↓
Phase 3: Query analysis
↓
Phase 4: Hybrid retrieval baseline
↓
Phase 5: QA generation + submission
↓
Phase 6: Evaluation + error analysis
↓
Phase 7: Reranker / LLM verifier
↓
Phase 8: Neo4j graph expansion
↓
Phase 9: Fine-tuning preparation
```

Baseline cần hoàn thành trước:

```text
Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
```

---

## 2. Tech stack

### 2.1. Core

```text
Python 3.11+
Pydantic
Polars
DuckDB
datasets
rapidfuzz
pytest
ruff
```

### 2.2. Search / Retrieval

```text
OpenSearch hoặc Elasticsearch: BM25 / exact phrase search
Qdrant: dense vector search
Neo4j: graph expansion từ Phase 8
```

### 2.3. Models

```text
Embedding:
- darklethelong/vnlegal-lal

Generator:
- Qwen3-8B qua vLLM hoặc Ollama
- Qwen2.5-7B-Instruct fallback

Reranker:
- chỉ thêm từ Phase 7
```

---

## 3. Cây thư mục mục tiêu

```text
Legal_Graph_RAG/
├── context.md
├── legal_rag_phase_plan_v3.md
├── codex_task_prompts_vi_v3.md
├── skills/
│
├── backend/
│   ├── __init__.py
│   ├── config/
│   ├── infrastructure/
│   ├── schema/
│   ├── knowledge_processing/
│   ├── indexing/
│   ├── query_analysis/
│   ├── retrieval/
│   ├── qa/
│   ├── prompts/
│   ├── evaluation/
│   └── submission/
│
├── data/
│   ├── raw/
│   │   └── R2AIStage1DATA.json
│   ├── processed/
│   └── outputs/
│
├── scripts/
├── tests/
├── notebooks/
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

# Phase 0 — Project Setup

## P0.T1 — Tạo skeleton project

### Mục tiêu

Tạo cây thư mục và package structure ban đầu.

### Codex Prompt

Dùng prompt: `P0.T1` trong `codex_task_prompts_vi_v3.md`.

### Deliverables

```text
backend/__init__.py
backend/config/__init__.py
backend/infrastructure/__init__.py
backend/schema/__init__.py
backend/knowledge_processing/__init__.py
backend/indexing/__init__.py
backend/query_analysis/__init__.py
backend/retrieval/__init__.py
backend/qa/__init__.py
backend/evaluation/__init__.py
backend/submission/__init__.py
scripts/
data/raw/
data/processed/
data/outputs/
tests/
```

### Acceptance Criteria

```text
[x] Tất cả folder mục tiêu tồn tại.
[x] Các Python package có __init__.py.
[x] Không tạo business logic ở task này.
[x] Không xóa file hiện có nếu không cần thiết.
```

### User-run commands

```bash
python -c "import backend; print('backend import ok')"
find backend -maxdepth 2 -type f | sort
```

### Expected result

```text
backend import ok
```

---

## P0.T2 — Config và settings

### Mục tiêu

Tạo config dùng chung cho path, model và retrieval.

### Codex Prompt

Dùng prompt: `P0.T2`.

### Deliverables

```text
backend/config/settings.py
backend/config/path_config.py
backend/config/retrieval_config.yaml
backend/config/model_config.yaml
.env.example
```

### Acceptance Criteria

```text
[x] Config đọc được từ YAML.
[x] Có default path cho raw/processed/output.
[x] Có default model names.
[x] Không hard-code path trong business logic.
[x] Có .env.example nhưng không commit secret.
```

### User-run commands

```bash
python - <<'PY'
from backend.config.settings import get_settings
s = get_settings()
print(s)
PY
```

### Expected result

```text
In ra settings object hoặc dict config hợp lệ, không lỗi import.
```

---

## P0.T3 — Docker compose baseline

### Mục tiêu

Tạo Docker services cần cho Phase 2 trở đi.

### Codex Prompt

Dùng prompt: `P0.T3`.

### Deliverables

```text
docker-compose.yml
```

### Required services

```text
qdrant
opensearch
neo4j
postgres optional
```

### Acceptance Criteria

```text
[ ] docker-compose.yml có qdrant.
[ ] docker-compose.yml có opensearch.
[ ] docker-compose.yml có neo4j nhưng Phase 1 chưa cần dùng.
[ ] Có volume persistent cho service cần thiết.
[ ] Có env sample rõ ràng.
```

### User-run commands

```bash
docker compose config
docker compose up -d qdrant opensearch
docker compose ps
```

### Expected result

```text
Docker compose config hợp lệ.
qdrant và opensearch ở trạng thái running/healthy hoặc ít nhất started.
```

---

# Phase 1 — Data Loading + Canonical Corpus

## Output chung của Phase 1

```text
data/processed/test_questions.parquet
data/processed/phapdien_articles.parquet
data/processed/anle_units.parquet
data/processed/legal_documents.parquet
data/processed/legal_articles.parquet
data/processed/phapdien_to_vbpl_map.parquet
```

---

## P1.T1 — Schema Pydantic

### Mục tiêu

Tạo schema nội bộ cho toàn pipeline.

### Codex Prompt

Dùng prompt: `P1.T1`.

### Deliverables

```text
backend/schema/question.py
backend/schema/legal_document.py
backend/schema/legal_article.py
backend/schema/phapdien_article.py
backend/schema/anle_unit.py
backend/schema/retrieval_result.py
backend/schema/submission.py
```

### Acceptance Criteria

```text
[ ] Có TestQuestion schema.
[ ] Có LegalDocument schema.
[ ] Có LegalArticle schema.
[ ] LegalArticle có relevant_article_string property.
[ ] LegalArticle có relevant_doc_string property.
[ ] Có schema cho submission item.
[ ] Pydantic validation chạy được.
```

### User-run commands

```bash
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

### Expected result

```text
04/2017/QH14|Luật 04/2017/QH14 Luật Hỗ trợ doanh nghiệp nhỏ và vừa|Điều 4
04/2017/QH14|Luật 04/2017/QH14 Luật Hỗ trợ doanh nghiệp nhỏ và vừa
```

---

## P1.T2 — Text normalization

### Mục tiêu

Tạo utilities chuẩn hóa text pháp luật tiếng Việt.

### Codex Prompt

Dùng prompt: `P1.T2`.

### Deliverables

```text
backend/knowledge_processing/normalize_text.py
backend/knowledge_processing/normalize_legal_doc.py
tests/test_normalize_text.py
```

### Required functions

```text
normalize_vietnamese_text(text: str | None) -> str
normalize_article_no(article_no: str | None) -> str
normalize_law_id(value: str | None) -> str
normalize_law_title(law_type: str | None, law_id: str | None, title: str | None) -> str
```

### Acceptance Criteria

```text
[ ] Unicode NFC.
[ ] NBSP được thay bằng space thường.
[ ] Gộp khoảng trắng lặp.
[ ] "Điều 04." -> "Điều 4".
[ ] "điều 7a" -> "Điều 7a".
[ ] Function xử lý None an toàn.
[ ] Có pytest cho normalization.
```

### User-run commands

```bash
pytest tests/test_normalize_text.py -q
python - <<'PY'
from backend.knowledge_processing.normalize_text import normalize_article_no
print(normalize_article_no("Điều 04."))
print(normalize_article_no("điều 7a"))
PY
```

### Expected result

```text
Điều 4
Điều 7a
```

---

## P1.T3 — Hugging Face generic loader

### Mục tiêu

Tạo helper chung để load HF datasets sang Polars.

### Codex Prompt

Dùng prompt: `P1.T3`.

### Deliverables

```text
backend/knowledge_processing/hf_loader.py
```

### Acceptance Criteria

```text
[ ] Có function load_hf_dataset_to_polars().
[ ] Support dataset_name, config_name, split.
[ ] Return Polars DataFrame.
[ ] Có save_parquet() helper.
[ ] Không gọi loader trong import-time.
```

### User-run commands

```bash
python - <<'PY'
from backend.knowledge_processing.hf_loader import load_hf_dataset_to_polars
df = load_hf_dataset_to_polars("tmquan/phapdien-moj-gov-vn", "articles", "train")
print(df.shape)
print(df.columns[:5])
PY
```

### Expected result

```text
In ra shape và columns của dataset phapdien.
```

---

## P1.T4 — Load testset

### Mục tiêu

Load file `R2AIStage1DATA.json` thành parquet.

### Codex Prompt

Dùng prompt: `P1.T4`.

### Deliverables

```text
backend/knowledge_processing/load_testset.py
scripts/01_load_testset.py
tests/test_load_testset.py
```

### Acceptance Criteria

```text
[ ] Validate JSON là list.
[ ] Mỗi item có id và question.
[ ] id convert được sang int.
[ ] question không rỗng sau normalize.
[ ] Không có duplicate id.
[ ] Output là data/processed/test_questions.parquet.
```

### User-run commands

```bash
python scripts/01_load_testset.py
python - <<'PY'
import polars as pl
df = pl.read_parquet("data/processed/test_questions.parquet")
print(df.shape)
print(df.head(3))
print(df["id"].n_unique())
PY
```

### Expected result

```text
Số dòng = 2000.
id unique = 2000.
```

---

## P1.T5 — Load phapdien

### Mục tiêu

Load `tmquan/phapdien-moj-gov-vn` config `articles`.

### Codex Prompt

Dùng prompt: `P1.T5`.

### Deliverables

```text
backend/knowledge_processing/load_phapdien.py
```

### Required output

```text
data/processed/phapdien_articles.parquet
```

### Required columns

```text
phapdien_id
topic_title
subject_title
chapter_title
article_title
content_text
source_note_text
related_note_text
source_url
source_links_json
```

### Acceptance Criteria

```text
[ ] Load được dataset phapdien.
[ ] content_text không rỗng với phần lớn rows.
[ ] source_note_text được giữ lại.
[ ] source_links được serialize thành JSON string.
[ ] Không dùng article_title làm citation chính thức.
```

### User-run commands

```bash
python - <<'PY'
from backend.knowledge_processing.load_phapdien import load_phapdien_articles
df = load_phapdien_articles("data/processed/phapdien_articles.parquet")
print(df.shape)
print(df.columns)
print(df.select("article_title", "content_text").head(3))
PY
```

### Expected result

```text
Tạo được phapdien_articles.parquet và in sample rows.
```

---

## P1.T6 — Load anle

### Mục tiêu

Load `tmquan/anle-toaan-gov-vn` config `sentences`.

### Codex Prompt

Dùng prompt: `P1.T6`.

### Deliverables

```text
backend/knowledge_processing/load_anle.py
```

### Required output

```text
data/processed/anle_units.parquet
```

### Acceptance Criteria

```text
[ ] Load sentence/paragraph-level units.
[ ] Có unit_id unique.
[ ] Có text không rỗng.
[ ] Không dùng embedding có sẵn từ dataset.
[ ] anle chỉ là auxiliary source.
```

### User-run commands

```bash
python - <<'PY'
from backend.knowledge_processing.load_anle import load_anle_sentences
df = load_anle_sentences("data/processed/anle_units.parquet")
print(df.shape)
print(df.columns)
print(df.head(3))
PY
```

### Expected result

```text
Tạo được anle_units.parquet và in sample rows.
```

---

## P1.T7 — Load VBPL documents

### Mục tiêu

Load `tmquan/vbpl-vn` thành document-level parquet.

### Codex Prompt

Dùng prompt: `P1.T7`.

### Deliverables

```text
backend/knowledge_processing/load_vbpl.py
```

### Required output

```text
data/processed/legal_documents.parquet
```

### Required columns

```text
doc_id
law_id
law_type
law_title
normalized_title
source_url
markdown
issue_date
effective_date
status
legal_area
```

### Acceptance Criteria

```text
[ ] Load được VBPL dataset.
[ ] Có markdown/body text.
[ ] normalized_title được tạo ổn định.
[ ] Có log cho rows thiếu law_id hoặc markdown.
[ ] Không extract article trong task này.
```

### User-run commands

```bash
python - <<'PY'
from backend.knowledge_processing.load_vbpl import load_vbpl_documents
df = load_vbpl_documents("data/processed/legal_documents.parquet")
print(df.shape)
print(df.columns)
print(df.select("law_id", "normalized_title").head(5))
PY
```

### Expected result

```text
Tạo được legal_documents.parquet.
```

---

## P1.T8 — Extract legal articles

### Mục tiêu

Tách Điều luật từ `legal_documents.parquet`.

### Codex Prompt

Dùng prompt: `P1.T8`.

### Deliverables

```text
backend/knowledge_processing/extract_articles.py
```

### Required output

```text
data/processed/legal_articles.parquet
```

### Acceptance Criteria

```text
[ ] Extract được article-level rows.
[ ] article_id format: law_id|law_title|Điều X.
[ ] article_id unique.
[ ] Không có article thiếu law_id/law_title/article_no/article_text.
[ ] Có log văn bản không extract được Điều.
[ ] Có test cho regex article extraction ở mức cơ bản.
```

### User-run commands

```bash
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

### Expected result

```text
Tạo được legal_articles.parquet.
unique article_id bằng số dòng.
```

---

## P1.T9 — Map phapdien to VBPL

### Mục tiêu

Map phapdien hits sang canonical legal articles.

### Codex Prompt

Dùng prompt: `P1.T9`.

### Deliverables

```text
backend/knowledge_processing/map_phapdien_to_vbpl.py
```

### Required output

```text
data/processed/phapdien_to_vbpl_map.parquet
```

### Acceptance Criteria

```text
[ ] Có phapdien_id.
[ ] Có legal_article_id.
[ ] Có law_id, law_title, article_no.
[ ] Có mapping_score.
[ ] Có mapping_method.
[ ] Mapping dưới threshold được log ra file/debug.
[ ] Không dùng phapdien article_title làm official citation.
```

### User-run commands

```bash
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

### Expected result

```text
Tạo được phapdien_to_vbpl_map.parquet với mapping_score.
```

---

## P1.T10 — Build corpus orchestration

### Mục tiêu

Gộp toàn bộ Phase 1 thành một script.

### Codex Prompt

Dùng prompt: `P1.T10`.

### Deliverables

```text
backend/knowledge_processing/build_corpus.py
scripts/01_build_corpus.py
```

### Acceptance Criteria

```text
[ ] scripts/01_build_corpus.py gọi các module Phase 1 theo thứ tự.
[ ] Script không chứa business logic lớn.
[ ] Có logging từng step.
[ ] Có option skip_existing nếu phù hợp.
[ ] Người dùng tự chạy script.
```

### User-run commands

```bash
python scripts/01_build_corpus.py
ls -lh data/processed
```

### Expected result

```text
Tạo đủ 6 parquet files của Phase 1.
```

## P1.T11 — Prepare Indexable Corpus

### Mục tiêu

Tạo lớp dữ liệu trung gian phục vụ indexing cho Phase 2, nhằm tránh đưa trực tiếp `legal_articles.parquet` và `phapdien_articles.parquet` vào OpenSearch/Qdrant khi dữ liệu còn có outlier quá dài hoặc row rỗng.

Task này **không thay đổi canonical corpus**. Các file canonical sau vẫn là source of truth:

```text
data/processed/legal_articles.parquet
data/processed/phapdien_articles.parquet
```

Thay vào đó, task này tạo các file derived/indexable:

```text
data/processed/legal_article_chunks.parquet
data/processed/phapdien_articles_index.parquet
```

Phase 2 sẽ index từ các file derived này.

---

### Bối cảnh sau Phase 1

Phase 1 đã build xong với kết quả:

```text
test_questions: 2.000 rows, unique id 2.000
phapdien_articles: 64.464 rows, có 406 rows empty content_text
anle_units: 273.379 rows, unit_id unique, không empty text
legal_documents: 146.555 rows, không thiếu law_id/markdown
legal_articles: 1.015.680 rows, article_id unique bằng số dòng, không thiếu required fields
phapdien_to_vbpl_map: 60.053 rows, không thiếu legal_article_id
mapping coverage phapdien: 93.16%
low-confidence/unmapped phapdien: 4.411 rows, đã có debug parquet
```

Risk cần xử lý trước Phase 2:

```text
1. legal_articles.article_text có outlier rất lớn, max khoảng 2.31M ký tự.
2. phapdien có 406 rows rỗng content_text.
3. 4.411 phapdien rows chưa map được, nhưng tạm thời defer vì không ảnh hưởng nguyên tắc citation.
```

---

### Nguyên tắc bắt buộc

```text
[ ] Không sửa trực tiếp legal_articles.parquet.
[ ] Không sửa trực tiếp phapdien_articles.parquet.
[ ] legal_articles.parquet vẫn là source of truth cho relevant_docs/relevant_articles.
[ ] Index corpus chỉ phục vụ retrieval.
[ ] Khi retrieval hit vào chunk, output cuối cùng vẫn phải group về parent article_id.
[ ] Không dùng chunk_id làm citation.
[ ] Không xử lý 4.411 unmapped phapdien trong task này.
```

---

### Deliverables

Tạo module:

```text
backend/knowledge_processing/prepare_index_corpus.py
```

Tạo script:

```text
scripts/01_prepare_index_corpus.py
```

Tạo output files:

```text
data/processed/legal_article_chunks.parquet
data/processed/phapdien_articles_index.parquet
data/processed/debug/legal_article_text_length_report.csv
data/processed/debug/legal_article_chunk_report.csv
data/processed/debug/phapdien_empty_content_report.csv
```

Tạo test nếu phù hợp:

```text
tests/test_prepare_index_corpus.py
```

---

### Output 1 — legal_article_chunks.parquet

Input:

```text
data/processed/legal_articles.parquet
```

Output:

```text
data/processed/legal_article_chunks.parquet
```

Schema đề xuất:

```text
chunk_id
article_id
law_id
law_title
article_no
article_title
chunk_index
chunk_text
chunk_char_len
source_url
domain
status
```

`chunk_id` format:

```text
{article_id}::chunk_{chunk_index:04d}
```

Chunking rules:

```text
[ ] Nếu article_text ngắn, tạo 1 chunk.
[ ] Nếu article_text quá dài, split thành nhiều chunks.
[ ] Không tạo chunk_text rỗng.
[ ] Không làm mất parent article_id.
[ ] chunk_text dùng cho BM25/vector index.
[ ] article_id dùng để group retrieval result về Điều luật canonical.
```

Config mặc định:

```yaml
max_chunk_chars: 3000
chunk_overlap_chars: 300
max_article_chars_for_single_doc: 12000
min_text_chars: 20
```

Gợi ý xử lý:

```text
- Ưu tiên split theo ranh giới đoạn/khoản/dòng nếu làm được.
- Nếu không tìm được ranh giới phù hợp, fallback split theo character window.
- Overlap không được tạo infinite loop.
- Article quá ngắn hoặc text lỗi cần được log, không làm crash pipeline.
```

---

### Output 2 — phapdien_articles_index.parquet

Input:

```text
data/processed/phapdien_articles.parquet
```

Output:

```text
data/processed/phapdien_articles_index.parquet
```

Yêu cầu:

```text
[ ] Loại khỏi index input các row có content_text null hoặc rỗng sau strip.
[ ] Không xóa row khỏi phapdien_articles.parquet gốc.
[ ] Giữ các field cần cho retrieval.
```

Fields cần giữ:

```text
phapdien_id
topic_title
subject_title
chapter_title
article_title
content_text
source_note_text
related_note_text
source_url
source_links_json
```

Các row rỗng được ghi vào:

```text
data/processed/debug/phapdien_empty_content_report.csv
```

---

### Output 3 — legal_article_text_length_report.csv

Tạo report:

```text
data/processed/debug/legal_article_text_length_report.csv
```

Fields tối thiểu:

```text
article_id
law_id
law_title
article_no
article_title
article_text_char_len
source_url
status
domain
```

Yêu cầu:

```text
[ ] Sort giảm dần theo article_text_char_len.
[ ] Dùng để audit các Điều luật outlier quá dài.
```

---

### Output 4 — legal_article_chunk_report.csv

Tạo report:

```text
data/processed/debug/legal_article_chunk_report.csv
```

Report cần có:

```text
total_articles
total_chunks
max_article_text_len
max_chunk_len
avg_chunks_per_article
articles_with_multiple_chunks
articles_skipped_if_any
max_chunk_chars
chunk_overlap_chars
max_article_chars_for_single_doc
min_text_chars
```

Có thể lưu dạng CSV một dòng để dễ đọc bằng Polars/Pandas.

---

### Required function

Trong `prepare_index_corpus.py`, tạo function chính:

```python
def prepare_indexable_corpus(
    legal_articles_path: str = "data/processed/legal_articles.parquet",
    phapdien_articles_path: str = "data/processed/phapdien_articles.parquet",
    output_legal_chunks_path: str = "data/processed/legal_article_chunks.parquet",
    output_phapdien_index_path: str = "data/processed/phapdien_articles_index.parquet",
    debug_dir: str = "data/processed/debug",
    max_chunk_chars: int = 3000,
    chunk_overlap_chars: int = 300,
    max_article_chars_for_single_doc: int = 12000,
    min_text_chars: int = 20,
) -> dict:
    ...
```

Return summary dict gồm:

```text
legal_articles_count
legal_chunks_count
phapdien_rows_count
phapdien_index_rows_count
phapdien_empty_rows_count
max_article_text_len
reports_created
```

---

### Script entrypoint

Tạo:

```text
scripts/01_prepare_index_corpus.py
```

Script cần hỗ trợ argparse:

```text
--max-chunk-chars
--chunk-overlap-chars
--min-text-chars
--max-article-chars-for-single-doc
```

Yêu cầu:

```text
[ ] Script chỉ gọi backend function.
[ ] Không chứa business logic lớn.
[ ] Có logging rõ từng bước.
[ ] In summary cuối cùng.
```

---

### Tests

Tạo:

```text
tests/test_prepare_index_corpus.py
```

Test tối thiểu:

```text
[ ] Short article tạo 1 chunk.
[ ] Long article tạo nhiều chunks.
[ ] chunk_id giữ parent article_id.
[ ] Overlap không tạo infinite loop.
[ ] Không có chunk_text rỗng.
[ ] phapdien empty content bị filter khỏi index output.
[ ] legal_articles canonical không bị modify.
```

---

### Acceptance Criteria

```text
[ ] legal_articles.parquet không bị sửa.
[ ] phapdien_articles.parquet không bị sửa.
[ ] Tạo được legal_article_chunks.parquet.
[ ] Tạo được phapdien_articles_index.parquet.
[ ] Tạo được legal_article_text_length_report.csv.
[ ] Tạo được legal_article_chunk_report.csv.
[ ] Tạo được phapdien_empty_content_report.csv.
[ ] legal_article_chunks.parquet có chunk_id unique.
[ ] Mỗi chunk có parent article_id.
[ ] Không có chunk_text rỗng.
[ ] phapdien_articles_index.parquet không có content_text rỗng.
[ ] Code có type hints.
[ ] Logic chunking có comment tiếng Việt.
[ ] Không xử lý 4.411 unmapped phapdien trong task này.
```

---

### User-run commands

Chạy test:

```bash
pytest tests/test_prepare_index_corpus.py -q
```

Chạy prepare index corpus:

```bash
python scripts/01_prepare_index_corpus.py
```

Kiểm tra output:

```bash
python - <<'PY'
import polars as pl
from pathlib import Path

files = [
    "data/processed/legal_article_chunks.parquet",
    "data/processed/phapdien_articles_index.parquet",
    "data/processed/debug/legal_article_text_length_report.csv",
    "data/processed/debug/legal_article_chunk_report.csv",
    "data/processed/debug/phapdien_empty_content_report.csv",
]

for f in files:
    p = Path(f)
    print(f, "exists=", p.exists())
    if p.exists():
        if f.endswith(".parquet"):
            df = pl.read_parquet(p)
        else:
            df = pl.read_csv(p)
        print("  shape:", df.shape)
        print(df.head(3))

chunks = pl.read_parquet("data/processed/legal_article_chunks.parquet")
print("chunk_id unique:", chunks["chunk_id"].n_unique(), "/", chunks.height)
print(
    "empty chunk_text:",
    chunks.filter(
        pl.col("chunk_text").is_null()
        | (pl.col("chunk_text").str.strip_chars() == "")
    ).height,
)

phapdien_idx = pl.read_parquet("data/processed/phapdien_articles_index.parquet")
print(
    "empty phapdien content_text:",
    phapdien_idx.filter(
        pl.col("content_text").is_null()
        | (pl.col("content_text").str.strip_chars() == "")
    ).height,
)
PY
```

---

### Expected result

```text
legal_article_chunks.parquet tồn tại
phapdien_articles_index.parquet tồn tại
debug reports tồn tại
chunk_id unique = số dòng chunks
empty chunk_text = 0
empty phapdien content_text = 0
```

---

### Phase 2 dependency update

Sau task này, Phase 2 không index trực tiếp full text từ:

```text
data/processed/legal_articles.parquet
data/processed/phapdien_articles.parquet
```

Thay vào đó, Phase 2 index từ:

```text
data/processed/legal_article_chunks.parquet
data/processed/phapdien_articles_index.parquet
data/processed/anle_units.parquet
```

Khi retrieval hit vào `legal_article_chunks`, hệ thống phải group kết quả về parent `article_id` trước khi article selection và submission builder xử lý.

---

# Phase 2 — Indexing

## Nguyên tắc chung của Phase 2

Phase 2 xây dựng các index phục vụ retrieval. Phase 2 **không sinh citation** và **không thay đổi canonical corpus**.

Nguồn dữ liệu bắt buộc:

```text
Legal BM25/vector retrieval:
- data/processed/legal_article_chunks.parquet

Phapdien BM25/vector retrieval:
- data/processed/phapdien_articles_index.parquet

Anle retrieval:
- data/processed/anle_units.parquet

Exact index / canonical lookup:
- data/processed/legal_articles.parquet
```

Quy tắc bắt buộc:

```text
[ ] Không index trực tiếp full article_text từ legal_articles.parquet vào BM25/vector legal retrieval.
[ ] BM25/vector legal retrieval phải dùng legal_article_chunks.parquet.
[ ] legal_articles.parquet chỉ dùng cho exact lookup, canonical registry, citation và submission.
[ ] chunk_id không được dùng làm citation.
[ ] Retrieval hits từ legal chunks phải giữ parent article_id.
[ ] Retrieval layer phải dedup/group chunk hits về article_id trước article selection.
[ ] Phapdien index phải dùng phapdien_articles_index.parquet, không dùng phapdien_articles.parquet gốc.
[ ] Neo4j không thuộc Phase 2; Neo4j chỉ triển khai ở Phase 8.
```

---

## P2.T1 — Infrastructure clients

### Codex Prompt

Dùng prompt: `P2.T1`.

### Deliverables

```text
backend/infrastructure/search_engine/opensearch_client.py
backend/infrastructure/vector_store/qdrant_client.py
backend/infrastructure/database/duckdb_client.py
```

### Acceptance Criteria

```text
[ ] OpenSearch client có health_check().
[ ] Qdrant client có health_check().
[ ] DuckDB helper đọc parquet được.
[ ] Không tạo index ở import-time.
```

### User-run commands

```bash
python - <<'PY'
from backend.infrastructure.database.duckdb_client import DuckDBClient
db = DuckDBClient()
print("duckdb ok")
PY
```

---

## P2.T2 — vnlegal-lal embedding wrapper

### Codex Prompt

Dùng prompt: `P2.T2`.

### Deliverables

```text
backend/infrastructure/embedding_models/vnlegal_lal.py
```

### Acceptance Criteria

```text
[ ] Có encode_query().
[ ] Có encode_documents().
[ ] Query có instruction prefix.
[ ] Document không có instruction prefix.
[ ] Output vector dimension = 1024 nếu model load đúng.
[ ] Có batching.
[ ] Có normalize vector.
[ ] Với vnlegal-lal, ưu tiên AutoModel + last-token pooling theo model card; không rely vào SentenceTransformer fallback mean pooling nếu đã có wrapper chuẩn.
```

### User-run commands

```bash
python - <<'PY'
from backend.infrastructure.embedding_models.vnlegal_lal import VNLegalLALEmbedder
m = VNLegalLALEmbedder(device="cuda", batch_size=2, max_length=512)
v = m.encode_query("Doanh nghiệp nhỏ và vừa là gì?")
print(len(v), v[:5])
PY
```

---

## P2.T3 — Build BM25 indexes

### Codex Prompt

Dùng prompt: `P2.T3`.

### Deliverables

```text
backend/indexing/build_bm25_index.py
```

### Inputs

```text
data/processed/legal_article_chunks.parquet
data/processed/phapdien_articles_index.parquet
data/processed/anle_units.parquet
```

### Indexes

```text
legal_article_chunks_bm25
phapdien_articles_bm25
anle_units_bm25
```

### Legal chunk indexed fields

```text
chunk_text
law_title
article_no
article_title
domain
status
```

### Legal chunk payload fields

```text
chunk_id
article_id
law_id
law_title
article_no
article_title
chunk_index
source_url
domain
status
```

### Acceptance Criteria

```text
[ ] Build được legal_article_chunks_bm25.
[ ] Build được phapdien_articles_bm25.
[ ] Build được anle_units_bm25.
[ ] Legal BM25 đọc legal_article_chunks.parquet, không đọc legal_articles.parquet.
[ ] Legal BM25 index dùng chunk_text làm text chính.
[ ] Payload legal BM25 giữ cả chunk_id và parent article_id.
[ ] Phapdien BM25 đọc phapdien_articles_index.parquet.
[ ] Có recreate flag.
[ ] Có max_rows/sample option nếu phù hợp.
```

### User-run commands

```bash
python - <<'PY'
from backend.indexing.build_bm25_index import build_all_bm25_indexes
build_all_bm25_indexes(recreate=True, max_rows=1000)
print("bm25 smoke indexes built")
PY
```

---

## P2.T4 — Build vector indexes

### Codex Prompt

Dùng prompt: `P2.T4`.

### Deliverables

```text
backend/indexing/build_vector_index.py
```

### Inputs

```text
data/processed/legal_article_chunks.parquet
data/processed/phapdien_articles_index.parquet
data/processed/anle_units.parquet
```

### Qdrant collections

```text
legal_article_chunks_dense
phapdien_articles_dense
anle_units_dense
```

### Legal chunk text format để embed

```text
Tên văn bản: {law_title}
Điều: {article_no}
Tiêu đề điều: {article_title}
Nội dung chunk:
{chunk_text}
```

### Legal chunk payload fields

```text
chunk_id
article_id
law_id
law_title
article_no
article_title
chunk_index
source_url
domain
status
```

### Acceptance Criteria

```text
[ ] Build được legal_article_chunks_dense.
[ ] Build được phapdien_articles_dense.
[ ] Build được anle_units_dense.
[ ] Legal vector index đọc legal_article_chunks.parquet, không đọc legal_articles.parquet.
[ ] Legal vector index embed chunk_text kèm legal context.
[ ] Payload giữ chunk_id và parent article_id.
[ ] Không dùng chunk_id làm canonical citation id.
[ ] Phapdien vector đọc phapdien_articles_index.parquet.
[ ] Có batching.
[ ] Có recreate flag.
[ ] Có resume/skip option nếu phù hợp.
[ ] Nếu đổi từ article-level sang chunk-level thì phải rebuild với recreate=True, resume=False.
[ ] Không trộn embedding từ mean pooling và last-token pooling trong cùng collection.
```

### User-run commands

```bash
python - <<'PY'
from backend.infrastructure.embedding_models.vnlegal_lal import VNLegalLALEmbedder
from backend.indexing.build_vector_index import build_all_vector_indexes

embedder = VNLegalLALEmbedder(device="cuda", batch_size=8, max_length=512)
build_all_vector_indexes(
    recreate=True,
    resume=False,
    embedder=embedder,
    max_rows=20,
)
print("chunk-level vector smoke test built")
PY
```

---

## P2.T5 — Build exact index

### Codex Prompt

Dùng prompt: `P2.T5`.

### Deliverables

```text
backend/indexing/build_exact_index.py
data/processed/exact_index.json hoặc parquet
```

### Input

```text
data/processed/legal_articles.parquet
```

### Acceptance Criteria

```text
[ ] Exact index vẫn đọc legal_articles.parquet.
[ ] Exact lookup theo law_id.
[ ] Exact lookup theo article_no.
[ ] Exact lookup theo law_id + article_no.
[ ] Extract được tài khoản kế toán nếu phù hợp.
[ ] Extract được deadline number nếu phù hợp.
[ ] Exact index load nhanh.
[ ] Không dùng legal_article_chunks.parquet cho exact citation registry.
```

### User-run commands

```bash
python - <<'PY'
from backend.indexing.build_exact_index import build_exact_index
idx = build_exact_index("data/processed/legal_articles.parquet", "data/processed/exact_index.json")
print(idx.keys())
PY
```

---
## Task ID: P2.T5-OPTIMIZE-EXACT-INDEX-RUNTIME

Bạn đang code trong repository `Legal_Graph_RAG`.

Trước khi code, hãy đọc:

* `context.md`
* `legal_rag_phase_plan_v3.md`
* `codex_task_prompts_vi_v3.md`
* `backend/indexing/build_exact_index.py` nếu đã tồn tại
* `tests/test_build_exact_index.py` nếu đã tồn tại
* `skills/11_code_quality_testing.md`

### Bối cảnh hiện tại

P2.T5 đã build được file:

```text
data/processed/exact_index.json
```

Kết quả kiểm tra:

```text
size_gb: ~1.9GB
article_count: 1,015,680
articles: 1,015,680
by_law_id: 51,522
by_article_no: 1,520
accounting_accounts: 726
deadline_numbers: 1,624
sanction_terms: 29,997
```

`exact_index.json` đọc được và không lỗi JSON. `articles` không chứa `article_text`, chỉ chứa metadata ngắn:

```text
article_id
law_id
law_title
article_no
article_title
source_url
domain
status
```

Vấn đề chính: `exact_index.json` quá lớn vì các inverted indexes lưu lặp lại `article_id` dài nhiều lần. Nếu Phase 4 runtime dùng `json.load()` file 1.9GB thì tốn RAM, startup chậm và không phù hợp để chạy retrieval nhiều lần.

- Nếu project đã chọn DuckDB làm runtime exact index, cập nhật deliverable thành data/processed/exact_index.duckdb.
- Không giữ mô tả bắt buộc exact_index/ folder Parquet nếu không còn triển khai hướng đó.

### Mục tiêu task

Tối ưu P2.T5 để tạo thêm exact index runtime-friendly dạng thư mục nhiều file Parquet/JSON metadata, thay vì phụ thuộc vào một file JSON lớn.

Mục tiêu mới:

```text
data/processed/exact_index/
├── articles.parquet
├── by_law_id.parquet
├── by_article_no.parquet
├── by_law_article.parquet
├── accounting_accounts.parquet
├── deadline_numbers.parquet
├── sanction_terms.parquet
└── metadata.json
```

Có thể giữ `data/processed/exact_index.json` như artifact debug/backward-compatible nếu code hiện tại cần, nhưng runtime Phase 4 nên ưu tiên đọc thư mục `data/processed/exact_index/`.

### Yêu cầu thiết kế bắt buộc

1. Exact index vẫn chỉ đọc:

```text
data/processed/legal_articles.parquet
```

2. Không đọc:

```text
data/processed/legal_article_chunks.parquet
```

3. Không dùng OpenSearch/Qdrant.

4. Không gọi LLM.

5. Không sinh `results.json`.

6. Không chọn final `relevant_articles`.

7. Không sửa BM25/vector index logic.

8. Không thay đổi canonical `legal_articles.parquet`.

9. Không dùng `chunk_id` trong exact index.

10. Exact index runtime artifact phải tránh lặp chuỗi `article_id` dài quá nhiều lần bằng cách dùng `article_idx` integer.

### Schema đề xuất

#### 1. `articles.parquet`

Mỗi dòng là một canonical article.

Required columns:

```text
article_idx
article_id
law_id
law_title
article_no
article_title
source_url
domain
status
normalized_law_id
normalized_law_title
normalized_article_no
relevant_doc_string
relevant_article_string
```

Yêu cầu:

```text
article_idx là int liên tục từ 0 đến n-1.
article_id unique.
Không có duplicate article_idx.
Không chứa article_text để tránh file quá lớn.
relevant_doc_string = law_id|law_title
relevant_article_string = law_id|law_title|article_no
```

#### 2. `by_law_id.parquet`

Long-table lookup:

```text
key
article_idx
```

Trong đó `key` là `normalized_law_id`.

#### 3. `by_article_no.parquet`

Long-table lookup:

```text
key
article_idx
```

Trong đó `key` là `normalized_article_no`.

Lưu ý: một `article_no` như “Điều 4” có thể map tới rất nhiều `article_idx`, không được assume unique.

#### 4. `by_law_article.parquet`

Long-table lookup cho law + article.

Required columns:

```text
key
article_idx
key_type
```

Trong đó `key_type` có thể là:

```text
law_id_article_no
law_title_article_no
```

Key nên được normalize ổn định, ví dụ:

```text
{normalized_law_id}::{normalized_article_no}
{normalized_law_title}::{normalized_article_no}
```

#### 5. `accounting_accounts.parquet`

Long-table lookup:

```text
key
article_idx
```

Trong đó `key` là mã tài khoản kế toán hoặc account pattern đã extract.

#### 6. `deadline_numbers.parquet`

Long-table lookup:

```text
key
article_idx
```

Trong đó `key` là các biểu thức thời hạn/số ngày/số tháng/năm đã extract nếu logic hiện tại đã có.

#### 7. `sanction_terms.parquet`

Long-table lookup:

```text
key
article_idx
```

Trong đó `key` là term/amount/pattern liên quan xử phạt nếu logic hiện tại đã có.

#### 8. `metadata.json`

Required fields:

```json
{
  "article_count": 1015680,
  "law_count": 51522,
  "by_law_id_rows": 0,
  "by_article_no_rows": 0,
  "by_law_article_rows": 0,
  "accounting_accounts_rows": 0,
  "deadline_numbers_rows": 0,
  "sanction_terms_rows": 0,
  "source_file": "data/processed/legal_articles.parquet",
  "format_version": "exact_index_parquet_v1"
}
```

Số rows phải ghi đúng theo artifact thực tế.

### Function/API cần có

Trong `backend/indexing/build_exact_index.py`, tạo hoặc sửa function:

```python
def build_exact_index(
    input_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    *,
    recreate: bool = False,
    write_legacy_json: bool = False,
) -> None:
    ...
```

Yêu cầu:

```text
input_path default = data/processed/legal_articles.parquet từ settings/path config nếu có.
output_dir default = data/processed/exact_index.
Nếu recreate=True thì xóa hoặc overwrite output_dir an toàn.
write_legacy_json=False mặc định để tránh tạo lại file JSON 1.9GB nếu không cần.
Nếu write_legacy_json=True thì có thể tạo exact_index.json backward-compatible.
```

Nếu hiện tại code đã có `build_exact_index()` signature khác, hãy giữ backward compatibility nếu hợp lý, nhưng ưu tiên runtime artifact mới.

### Runtime helper optional nhưng khuyến nghị

Nếu phù hợp, tạo helper class nhẹ:

```python
class ExactIndexStore:
    def __init__(self, index_dir: str | Path):
        ...

    def load_articles(self) -> pl.DataFrame:
        ...

    def lookup_by_law_id(self, normalized_law_id: str) -> pl.DataFrame:
        ...

    def lookup_by_article_no(self, normalized_article_no: str) -> pl.DataFrame:
        ...

    def lookup_by_law_article(self, key: str) -> pl.DataFrame:
        ...
```

Không bắt buộc phải tối ưu bằng DuckDB ngay, nhưng nếu dùng DuckDB để query Parquet lazy được thì càng tốt. Không được load toàn bộ `exact_index.json` trong runtime helper.

### Files dự kiến sửa/tạo

Có thể sửa/tạo:

```text
backend/indexing/build_exact_index.py
tests/test_build_exact_index.py
scripts/02_build_exact_index.py
```

Nếu đã có file tương ứng, cập nhật thay vì tạo duplicate.

Không sửa:

```text
backend/indexing/build_bm25_index.py
backend/indexing/build_vector_index.py
backend/retrieval/*
```

trừ khi thật sự cần cập nhật import nhỏ và phải báo rõ trước.

### Acceptance Criteria

* [ ] `build_exact_index(recreate=True)` tạo được thư mục `data/processed/exact_index/`.
* [ ] Tạo đủ các files:

  * `articles.parquet`
  * `by_law_id.parquet`
  * `by_article_no.parquet`
  * `by_law_article.parquet`
  * `accounting_accounts.parquet`
  * `deadline_numbers.parquet`
  * `sanction_terms.parquet`
  * `metadata.json`
* [ ] `articles.parquet` có `article_idx` integer unique.
* [ ] `articles.parquet` có `article_id` unique.
* [ ] `articles.parquet` không chứa `article_text`.
* [ ] Inverted indexes dùng `article_idx`, không dùng lặp `article_id`.
* [ ] `relevant_doc_string` đúng format `law_id|law_title`.
* [ ] `relevant_article_string` đúng format `law_id|law_title|article_no`.
* [ ] `by_article_no.parquet` cho phép một key map nhiều `article_idx`.
* [ ] `by_law_article.parquet` hỗ trợ cả key theo law_id + article_no và law_title + article_no.
* [ ] `metadata.json` ghi đúng row counts.
* [ ] Không gọi OpenSearch/Qdrant/LLM.
* [ ] Không chạy lệnh thay tôi.

### Test cần thêm/cập nhật

Tạo/cập nhật `tests/test_build_exact_index.py`.

Test tối thiểu dùng fixture nhỏ, không dùng full corpus:

1. Build exact index từ fixture `legal_articles.parquet` nhỏ.
2. Output đủ files.
3. `articles.parquet` không có `article_text`.
4. `article_idx` unique.
5. `article_id` unique.
6. `relevant_doc_string` đúng.
7. `relevant_article_string` đúng.
8. `by_law_article` lookup được đúng article theo law_id + article_no.
9. `by_law_article` lookup được đúng article theo law_title + article_no.
10. `by_article_no` có thể trả nhiều article cho cùng “Điều 1”.
11. `metadata.json` có `format_version = exact_index_parquet_v1`.

### Lệnh tôi sẽ tự chạy

Sau khi bạn code xong, tôi sẽ chạy:

```bash
pytest tests/test_build_exact_index.py -q
```

Build exact index full:

```bash
python - <<'PY'
from backend.indexing.build_exact_index import build_exact_index

build_exact_index(recreate=True, write_legacy_json=False)
print("runtime-friendly exact index built")
PY
```

Validate output:

```bash
python - <<'PY'
import json
from pathlib import Path
import polars as pl

index_dir = Path("data/processed/exact_index")

print("files:", sorted(p.name for p in index_dir.iterdir()))

with (index_dir / "metadata.json").open("r", encoding="utf-8") as f:
    meta = json.load(f)

print(meta)

articles = pl.read_parquet(index_dir / "articles.parquet")
print("articles:", articles.shape)
print("article_id unique:", articles["article_id"].n_unique())
print("article_idx unique:", articles["article_idx"].n_unique())
print("has article_text:", "article_text" in articles.columns)

for name in [
    "by_law_id.parquet",
    "by_article_no.parquet",
    "by_law_article.parquet",
    "accounting_accounts.parquet",
    "deadline_numbers.parquet",
    "sanction_terms.parquet",
]:
    df = pl.read_parquet(index_dir / name)
    print(name, df.shape, df.columns)
PY
```

Expected:

* `articles` khoảng 1,015,680 rows.
* `article_id unique` = số rows.
* `article_idx unique` = số rows.
* `has article_text: False`.
* Các inverted index có columns gồm `key`, `article_idx`, và thêm `key_type` nếu cần.
* Tổng size thư mục `exact_index/` phải nhỏ hơn đáng kể so với `exact_index.json` 1.9GB.

### Quy trình làm việc bắt buộc

Trước khi sửa code, hãy báo cáo:

```text
Scope bạn hiểu:
- ...

Files dự kiến sửa:
- ...

Test command tôi cần chạy:
- ...
```

Sau đó dừng và chờ tôi xác nhận, trừ khi tôi ghi rõ “triển khai luôn”.

Sau khi hoàn thành, báo cáo:

```text
Files changed:
- ...

Logic thay đổi:
- ...

Acceptance Criteria:
- [x] ...
- [ ] ...

Test result:
- Chưa chạy — người dùng cần chạy lệnh bên dưới.

Risk còn lại:
- ...

Lệnh tôi cần chạy:
- ...
```

## P2.T6 — Build indexes orchestration

### Codex Prompt

Dùng prompt: `P2.T6`.

### Deliverables

```text
scripts/02_build_indexes.py
```

### Acceptance Criteria

```text
[ ] Script gọi BM25, vector, exact builders.
[ ] Có logging từng step.
[ ] Không chứa business logic lớn.
[ ] Có option --only bm25|dense|exact nếu phù hợp.
[ ] Có option --max-rows/sample-size nếu phù hợp.
[ ] Legal BM25/dense orchestration dùng legal_article_chunks.parquet.
[ ] Exact orchestration dùng legal_articles.parquet.
[ ] Người dùng tự chạy script.
```

### User-run commands

```bash
python scripts/02_build_indexes.py --only bm25 --max-rows 1000
python scripts/02_build_indexes.py --only dense --max-rows 20
python scripts/02_build_indexes.py --only exact
```


# Phase 3 — Query Analysis

## P3.T1 — Domain router

### Codex Prompt

Dùng prompt: `P3.T1`.

### Deliverables

```text
backend/query_analysis/domain_router.py
tests/test_domain_router.py
```

### Acceptance Criteria

```text
[ ] classify_domain(question) chạy được.
[ ] Có domain confidence.
[ ] Có domain other fallback.
[ ] Không hard-filter retrieval.
```

### User-run commands

```bash
pytest tests/test_domain_router.py -q
```

---

## P3.T2 — Answer type classifier

### Codex Prompt

Dùng prompt: `P3.T2`.

### Deliverables

```text
backend/query_analysis/answer_type_classifier.py
tests/test_answer_type_classifier.py
```

### Acceptance Criteria

```text
[ ] classify_answer_type(question) chạy được.
[ ] Nhận diện deadline/amount/sanction/procedure/dossier/conditions/yes_no/accounting_account.
[ ] Có fallback general/definition/multi_part.
```

### User-run commands

```bash
pytest tests/test_answer_type_classifier.py -q
```

---

## P3.T3 — Complexity detector

### Codex Prompt

Dùng prompt: `P3.T3`.

### Deliverables

```text
backend/query_analysis/complexity_detector.py
tests/test_complexity_detector.py
```

### Acceptance Criteria

```text
[ ] Detect single_hop.
[ ] Detect multi_hop với các cue: vừa, đồng thời, sau đó, trong khi.
[ ] Multiple domain signals có thể tăng multi-hop score.
```

### User-run commands

```bash
pytest tests/test_complexity_detector.py -q
```

---

## P3.T4 — Legal entity extractor

### Codex Prompt

Dùng prompt: `P3.T4`.

### Deliverables

```text
backend/query_analysis/legal_entity_extractor.py
tests/test_legal_entity_extractor.py
```

### Acceptance Criteria

```text
[ ] Extract Điều X.
[ ] Extract tên/mã Luật/Nghị định/Thông tư nếu có.
[ ] Extract tài khoản kế toán.
[ ] Extract ngày/tháng/năm/thời hạn.
[ ] Extract mức tiền phạt.
```

### User-run commands

```bash
pytest tests/test_legal_entity_extractor.py -q
```

---

## P3.T5 — Query expander

### Codex Prompt

Dùng prompt: `P3.T5`.

### Deliverables

```text
backend/query_analysis/query_expander.py
tests/test_query_expander.py
```

### Acceptance Criteria

```text
[ ] DNNVV ↔ doanh nghiệp nhỏ và vừa.
[ ] hóa đơn đỏ ↔ hóa đơn GTGT.
[ ] cho nghỉ việc ↔ chấm dứt hợp đồng lao động.
[ ] trả nợ trước hạn ↔ tất toán sớm.
[ ] Expansion không làm mất query gốc.
```

### User-run commands

```bash
pytest tests/test_query_expander.py -q
```

---

## P3.T6 — Analyze questions orchestration

### Codex Prompt

Dùng prompt: `P3.T6`.

### Deliverables

```text
backend/query_analysis/analyze_question.py
scripts/03_analyze_questions.py
```

### Required output

```text
data/processed/test_questions_analyzed.parquet
```

### Acceptance Criteria

```text
[ ] 2.000 câu có domain.
[ ] 2.000 câu có answer_type.
[ ] 2.000 câu có complexity.
[ ] Có legal_entities_json.
[ ] Có expanded_queries_json.
```

### User-run commands

```bash
python scripts/03_analyze_questions.py
python - <<'PY'
import polars as pl
df = pl.read_parquet("data/processed/test_questions_analyzed.parquet")
print(df.shape)
print(df.select("id", "domain", "answer_type", "complexity").head(10))
PY
```

---

# Phase 4 — Hybrid Retrieval Baseline

## P4.T1 — BM25 retriever

### Codex Prompt

Dùng prompt: `P4.T1`.

### Deliverables

```text
backend/retrieval/bm25_retriever.py
```

### Acceptance Criteria

```text
[ ] search_legal_articles() thực chất search trên legal_article_chunks_bm25.
[ ] search_phapdien().
[ ] search_anle().
[ ] Return normalized RetrievalHit objects.
[ ] Không trả raw OpenSearch response trực tiếp cho tầng trên.
[ ] Legal BM25 hit phải return canonical article_id.
[ ] chunk_id chỉ nằm trong metadata.
[ ] Nếu nhiều chunk cùng article_id, retriever hoặc fusion layer phải dedup/group về article_id.
[ ] Không expose chunk_id như citation id.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.bm25_retriever import BM25Retriever
r = BM25Retriever()
hits = r.search_legal_articles("doanh nghiệp nhỏ và vừa", top_k=5)
print(hits[:2])
PY
```

---
## P4.T2 — Dense retriever

### Codex Prompt

Dùng prompt: `P4.T2`.

### Deliverables

```text
backend/retrieval/dense_retriever.py
```

### Acceptance Criteria

```text
[ ] search_legal_articles_dense() thực chất search trên legal_article_chunks_dense.
[ ] search_phapdien_dense().
[ ] search_anle_dense().
[ ] Dùng VNLegalLALEmbedder.encode_query().
[ ] Return normalized RetrievalHit objects.
[ ] Legal dense hit phải return canonical article_id.
[ ] chunk_id chỉ nằm trong metadata.
[ ] Nếu nhiều chunk cùng article_id, retriever hoặc fusion layer phải dedup/group về article_id.
[ ] Không expose chunk_id như citation id.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.dense_retriever import DenseRetriever
r = DenseRetriever()
hits = r.search_legal_articles_dense("doanh nghiệp nhỏ và vừa", top_k=5)
print(hits[:2])
PY
```

---
## P4.T3 — Exact retriever

### Codex Prompt

Dùng prompt: `P4.T3`.

### Note

- Runtime chính dùng exact_index.duckdb.
- exact_index.json chỉ legacy/debug nếu còn.
- Strong law_id_article_no match không append fallback article_no_only/law_id_only.

### Deliverables

```text
backend/retrieval/exact_retriever.py
```

### Acceptance Criteria

```text
[ ] Detect Điều X trong question.
[ ] Detect mã văn bản nếu có.
[ ] Detect tài khoản kế toán nếu có.
[ ] Return canonical LegalArticle candidate IDs.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.exact_retriever import ExactRetriever
r = ExactRetriever("data/processed/exact_index.duckdb")
print(r.search("Theo Điều 4 Luật Hỗ trợ DNNVV thì sao?", top_k=5))
PY
```

---

## P4.T4 — Phapdien retriever + mapper

### Codex Prompt

Dùng prompt: `P4.T4`.

### Deliverables

```text
backend/retrieval/phapdien_retriever.py
```

### Acceptance Criteria

```text
[ ] Search phapdien BM25/dense hits.
[ ] Map phapdien_id sang legal_article_id bằng phapdien_to_vbpl_map.
[ ] Không return phapdien article_title làm citation.
[ ] Có mapping_score trong output.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.phapdien_retriever import PhapdienMappedRetriever
r = PhapdienMappedRetriever()
hits = r.search_and_map("hỗ trợ doanh nghiệp nhỏ và vừa", top_k=5)
print(hits[:2])
PY
```

---

## P4.T5 — RRF fusion

### Codex Prompt

Dùng prompt: `P4.T5`.

### Deliverables

```text
backend/retrieval/fusion.py
tests/test_fusion.py
```

### Acceptance Criteria

```text
[ ] reciprocal_rank_fusion() đúng công thức.
[ ] Merge duplicate article_id.
[ ] Có source contribution.
[ ] Có score_boost() tách riêng.
[ ] Có pytest cho RRF.
```

### User-run commands

```bash
pytest tests/test_fusion.py -q
```

---

## P4.T6 — Article selector

### Codex Prompt

Dùng prompt: `P4.T6`.

### Deliverables

```text
backend/retrieval/article_selector.py
tests/test_article_selector.py
```

### Acceptance Criteria

```text
[ ] deadline/accounting_account max 4.
[ ] yes_no max 5.
[ ] procedure/dossier max 7.
[ ] sanction max 6.
[ ] conditions/obligations max 8.
[ ] multi_hop max 12.
[ ] Có dedup.
[ ] Không chọn article dưới threshold quá thấp nếu có score.
```

### User-run commands

```bash
pytest tests/test_article_selector.py -q
```

---

## P4.T7 — Hybrid retrieval orchestrator

### Codex Prompt

Dùng prompt: `P4.T7`.

### Deliverables

```text
backend/retrieval/hybrid_retrieval.py
```

### Acceptance Criteria

```text
[ ] Gọi BM25 legal.
[ ] Gọi dense legal.
[ ] Gọi exact.
[ ] Gọi phapdien mapped.
[ ] RRF fusion.
[ ] Article selection.
[ ] Output selected canonical LegalArticle IDs.
[ ] Không dùng LLM.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.hybrid_retrieval import HybridLegalRetriever
r = HybridLegalRetriever()
res = r.retrieve("Doanh nghiệp nhỏ và vừa được hỗ trợ những gì?")
print(res)
PY
```

---

## P4.T8 — Run retrieval script

### Codex Prompt

Dùng prompt: `P4.T8`.

### Deliverables

```text
scripts/04_run_retrieval.py
```

### Required output

```text
data/outputs/retrieval_results.jsonl
```

### Acceptance Criteria

```text
[ ] Script đọc test_questions_analyzed.parquet.
[ ] Ghi retrieval_results.jsonl.
[ ] Mỗi row có id, question, selected_articles.
[ ] selected_articles chỉ chứa canonical article IDs.
[ ] Có logging tiến độ.
```

### User-run commands

```bash
python scripts/04_run_retrieval.py
head -n 3 data/outputs/retrieval_results.jsonl
```

---

# Phase 5 — QA Generation + Submission

## P5.T1 — LLM client

### Codex Prompt

Dùng prompt: `P5.T1`.

### Deliverables

```text
backend/infrastructure/gen_llm_models/vllm_client.py
backend/infrastructure/gen_llm_models/qwen_client.py
```

### Acceptance Criteria

```text
[ ] Client configurable endpoint/model.
[ ] temperature default = 0.
[ ] Có timeout/retry cơ bản.
[ ] Không gọi LLM ở import-time.
```

### User-run commands

```bash
python - <<'PY'
from backend.infrastructure.gen_llm_models.vllm_client import VLLMClient
print("client import ok")
PY
```

---

## P5.T2 — Answer templates + prompt

### Codex Prompt

Dùng prompt: `P5.T2`.

### Deliverables

```text
backend/qa/answer_templates.py
backend/prompts/legal_qa_prompt.txt
```

### Acceptance Criteria

```text
[ ] Có template general.
[ ] Có template deadline.
[ ] Có template sanction.
[ ] Có template procedure/dossier.
[ ] Có template yes_no.
[ ] Prompt yêu cầu chỉ dùng selected_articles.
[ ] Prompt yêu cầu nhắc Điều X.
```

### User-run commands

```bash
python - <<'PY'
from backend.qa.answer_templates import build_answer_prompt
print(build_answer_prompt(question="Câu hỏi test", articles=[], answer_type="general")[:500])
PY
```

---

## P5.T3 — Answer generator

### Codex Prompt

Dùng prompt: `P5.T3`.

### Deliverables

```text
backend/qa/answer_generator.py
```

### Acceptance Criteria

```text
[ ] Input gồm question, selected_articles, answer_type.
[ ] Build context từ selected_articles.
[ ] Gọi LLM client.
[ ] Không sinh relevant_docs/relevant_articles.
[ ] Có fallback nếu selected_articles rỗng.
```

### User-run commands

```bash
python - <<'PY'
from backend.qa.answer_generator import AnswerGenerator
print("answer generator import ok")
PY
```

---

## P5.T4 — Citation postprocess

### Codex Prompt

Dùng prompt: `P5.T4`.

### Deliverables

```text
backend/qa/citation_postprocess.py
tests/test_citation_postprocess.py
```

### Acceptance Criteria

```text
[ ] Kiểm tra answer có nhắc Điều X đã chọn.
[ ] Append "Căn cứ pháp lý" nếu thiếu.
[ ] Không thêm Điều ngoài selected_articles.
[ ] Có pytest.
```

### User-run commands

```bash
pytest tests/test_citation_postprocess.py -q
```

---

## P5.T5 — Submission builder

### Codex Prompt

Dùng prompt: `P5.T5`.

### Deliverables

```text
backend/submission/build_results.py
backend/submission/validate_results.py
backend/submission/make_zip.py
tests/test_submission_validation.py
```

### Acceptance Criteria

```text
[ ] results.json là JSON list.
[ ] Mỗi item có id, question, answer, relevant_docs, relevant_articles.
[ ] relevant_docs derive từ selected_articles.
[ ] relevant_articles derive từ canonical LegalArticle.
[ ] Validate duplicate id.
[ ] Validate format relevant_docs.
[ ] Validate format relevant_articles.
[ ] Zip chỉ chứa results.json ở root.
```

### User-run commands

```bash
pytest tests/test_submission_validation.py -q
```

---

## P5.T6 — QA + submission scripts

### Codex Prompt

Dùng prompt: `P5.T6`.

### Deliverables

```text
scripts/05_generate_answers.py
scripts/06_build_submission.py
scripts/07_validate_submission.py
```

### Acceptance Criteria

```text
[ ] generate_answers đọc retrieval_results.jsonl.
[ ] build_submission tạo results.json.
[ ] validate_submission kiểm tra schema/format.
[ ] Scripts không chứa business logic lớn.
[ ] Người dùng tự chạy scripts.
```

### User-run commands

```bash
python scripts/05_generate_answers.py
python scripts/06_build_submission.py
python scripts/07_validate_submission.py
ls -lh data/outputs/results.json data/outputs/submission.zip
```

---

# Phase 6 — Evaluation, Error Analysis & Iterative Hardening

## Tổng hợp kế hoạch thực tế đã triển khai

## 1. Mục tiêu thực tế của Phase 6

Phase 6 được triển khai nhằm đánh giá chất lượng pipeline sau Phase 5, phát hiện các nhóm lỗi chính trong kết quả QA/submission và thực hiện các vòng cải thiện có kiểm soát trước khi chuyển sang Phase 7.

Trọng tâm thực tế của Phase 6 gồm:

* Xây dựng metric và error analysis report.
* Phát hiện lỗi citation ngoài selected context.
* Giảm lỗi `too_many_selected_articles`.
* Giảm lỗi answer bị truncate.
* Làm sạch lỗi hiển thị metadata legacy trong answer.
* Phân tích residual metadata/canonical legacy để quyết định có cleanup hay defer sang nhánh riêng.
* Không sử dụng Phase 6 để triển khai reranker, Neo4j hoặc fine-tuning.

---

## 2. Baseline đầu vào của Phase 6

Sau Phase 5, hệ thống đã có baseline QA/submission:

* Retrieval baseline: `data/outputs/retrieval_results.jsonl`
* Generated answers baseline: `data/outputs/generated_answers_v2_merged.jsonl`
* Results baseline: `data/outputs/results_v2.json`
* Submission baseline: `data/outputs/submission_v2.zip`

Baseline ban đầu phát hiện một số nhóm lỗi chính:

* Answer thiếu hoặc yếu căn cứ.
* Answer có citation ngoài selected articles.
* Một số câu có quá nhiều selected articles.
* Một số câu trả lời bị truncate.
* Một số selected/citation chứa metadata legacy như `Không số`.

---

## 3. Các task thực tế đã triển khai

## P6.T1 — Metrics

Đã triển khai metric cơ bản phục vụ đánh giá retrieval/QA:

* precision
* recall
* F2
* hit@k
* MRR

Trạng thái:

```text
P6.T1 — DONE / VERIFIED
```

Vai trò:

* Tạo nền tảng đo lường cho các vòng cải thiện sau.
* Không thay đổi retrieval/QA/submission.

---

## P6.T2 — Error analysis report

Đã triển khai error analysis report để tạo:

* `low_confidence_questions.csv`
* `retrieval_debug_report.csv`
* issue categories
* summary theo nhóm lỗi

Trạng thái:

```text
P6.T2 — DONE / VERIFIED
```

Vai trò:

* Làm cơ sở phát hiện lỗi và quyết định các round R tiếp theo.
* Không cần gold labels vẫn tạo được report mô tả lỗi.

---

## P6.R1 — Article text fallback

Mục tiêu:

* Xử lý lỗi selected article không có hoặc thiếu `article_text`.
* Đảm bảo answer generator có context pháp lý để sinh câu trả lời.

Kết quả:

* Lỗi liên quan empty/missing article text được xử lý.
* Tăng độ ổn định cho QA generation.

Trạng thái:

```text
P6.R1 — VERIFIED
```

---

## P6.R2 — Fair context truncation

Mục tiêu:

* Cải thiện cách cắt context khi nhiều điều luật được chọn.
* Tránh điều đầu tiên chiếm toàn bộ context budget.

Kết quả:

* Context được phân bổ công bằng hơn giữa các selected articles.
* Giảm rủi ro mất căn cứ ở các câu multi-law.

Trạng thái:

```text
P6.R2 — VERIFIED
```

---

## P6.R3 — Unsupported citation detection

Mục tiêu:

* Phát hiện trường hợp LLM viện dẫn điều/văn bản không nằm trong `selected_articles`.

Deliverables chính:

* `backend/evaluation/unsupported_citations.py`
* update `backend/evaluation/error_analysis.py`
* `unsupported_citations_report.csv`

Kết quả ban đầu:

* Phát hiện được lỗi unsupported citation.
* Tuy nhiên regex ban đầu bị over-capture, tạo false positive.

Trạng thái:

```text
P6.R3 — DONE / NEED TIGHTENING
```

---

## P6.R3.1 / P6.R3.2 — Tighten unsupported citation extraction

Mục tiêu:

* Giảm false positive trong unsupported citation detector.
* Không quét toàn answer bằng regex quá rộng.
* Chỉ flag citation mạnh có đủ `Điều X + law_id/law_title`.

Các cải tiến:

* Tách answer thành segment ngắn.
* Giới hạn khoảng cách giữa `Điều X` và `law_id`.
* Bỏ qua đoạn `Lưu ý` hoặc `Căn cứ pháp lý` bị over-capture.
* Xử lý thêm edge cases của law_id.

Kết quả:

* Unsupported citation detector ổn định hơn.
* Giảm đáng kể false positive.

Trạng thái:

```text
P6.R3.1 / P6.R3.2 — VERIFIED
```

---

## P6.R4 — Harden QA prompt

Mục tiêu:

* Siết prompt QA để LLM chỉ sử dụng selected articles.
* Hạn chế sinh citation ngoài context.
* Yêu cầu answer bám điều luật được cung cấp.

Kết quả sau P6.R4 và fix ID 418:

```text
total_questions: 2000
low_confidence_count: 454
unsupported_citation_count: 0
legacy_or_unknown_law_id: 231
too_many_selected_articles: 216
answer_maybe_truncated: 52
answer_insufficient_basis: 6
```

Best file sau P6.R4:

```text
data/outputs/generated_answers_v2_p6r4_merged_for_eval_fix_id418.jsonl
```

Trạng thái:

```text
P6.R4 — VERIFIED
```

Ý nghĩa:

* Đã đưa unsupported citation về 0.
* Các lỗi còn lại chuyển sang nhóm selector/context/metadata.

---

## P6.R5 — Too-many-selected analysis

Mục tiêu:

* Phân tích 216 case `too_many_selected_articles`.

Kết quả:

```text
total_too_many_selected_cases: 216
selected_count_distribution: 12 -> 216
cross_law_possible_noise: 174
legacy_or_version_noise: 34
answer_truncation_risk: 5
insufficient_basis_risk: 3
```

Output:

```text
data/outputs/error_analysis_v2_p6r5_too_many_selected/
```

Trạng thái:

```text
P6.R5 — VERIFIED
```

Ý nghĩa:

* `too_many_selected_articles` chủ yếu đến từ cross-law noise và legacy/version overlap.
* Cần selector tightening thay vì prompt-only.

---

## P6.R5b — Selector tightening strategy report

Mục tiêu:

* Lập chiến lược giảm selected articles nhưng hạn chế recall loss.

Kết quả:

```text
report_rows: 216
dominant_issue: cross_law_possible_noise
recommended_next_task: P6.R6_selector_tightening_experiment
metadata_anomaly_count: 271
empty_law_title: 91
law_id_title_mismatch_suspected: 90
legacy_version_overlap: 90
```

Output:

```text
data/outputs/error_analysis_v2_p6r5b_strategy/
```

Trạng thái:

```text
P6.R5b — VERIFIED
```

Ý nghĩa:

* Nên xử lý bằng selector tightening có kiểm soát.
* Không nên regenerate toàn bộ hoặc tăng prompt context tùy tiện.

---

## P6.R6a — Selector parser fix & strict tightening

Mục tiêu:

* Sửa parser `selected_articles` để hỗ trợ list string `article_id`.
* Thử nghiệm strict tightening.

Kết quả:

```text
baseline selected distribution:
4: 275
5: 184
6: 110
7: 851
8: 364
12: 216

strict tightened distribution:
4: 275
5: 547
6: 462
7: 487
8: 229

too_many_selected_cases_after_tightening: 0
possible_recall_loss_cases: 69
```

Trạng thái:

```text
P6.R6a — FIX VERIFIED
```

Ý nghĩa:

* Parser đã đúng.
* Strict config giảm too_many về 0 nhưng quá aggressive, có recall loss risk.

---

## P6.R6b — Selector tightening grid

Mục tiêu:

* So sánh nhiều cấu hình selector tightening.

Các config đã thử:

* `baseline_strict`
* `balanced_9_6`
* `balanced_10_6`
* `soft_10_7`
* `count_only_10`
* `law_cap_only_7`

Kết quả ban đầu:

* `soft_10_7` có vẻ cân bằng.
* Tuy nhiên sau đó phát hiện error analysis flag `too_many_selected_articles` từ selected count >= 10.
* `soft_10_7` vẫn còn 122 case selected count = 10.

Trạng thái:

```text
P6.R6b — VERIFIED / NOT FINAL CONFIG
```

---

## P6.R6c — Regenerate with soft_10_7

Mục tiêu:

* Regenerate answer cho subset bị ảnh hưởng bởi `soft_10_7`.

Kết quả sau fix ID 1782:

```text
low_confidence_count: 371
unsupported_citation_count: 0
legacy_or_unknown_law_id: 215
too_many_selected_articles: 122
answer_maybe_truncated: 40
answer_insufficient_basis: 18
```

Trạng thái:

```text
P6.R6c — RUNTIME COMPLETED / NOT FINAL
```

Ý nghĩa:

* `soft_10_7` cải thiện nhưng không đạt vì còn 122 too_many.
* Cần threshold-aligned selector config.

---

## P6.R6d — Threshold-aligned selector tuning

Mục tiêu:

* Tạo grid config align với threshold thực tế của error analysis.
* Đảm bảo selected count < 10.

Các config thử:

* `soft_9_7`
* `soft_9_8`
* `count_only_9`
* `law_cap_8_count_9`
* `balanced_9_7_no_metadata`

Kết quả:

```text
too_many_by_error_threshold_after: 0
rows_selected_count_ge_10_after: 0
possible_recall_loss_cases: 1
```

Config được chọn:

```text
soft_9_8
```

Lý do chọn:

* Giảm `too_many_selected_articles` về 0.
* Giữ metadata penalty.
* Giữ same-law coherence.
* Ít aggressive hơn strict config.

Best retrieval file:

```text
data/outputs/error_analysis_v2_p6r6d_selector_tuning_threshold_aligned/config_soft_9_8/retrieval_results_p6r6_tightened.jsonl
```

Trạng thái:

```text
P6.R6d — VERIFIED
```

---

## P6.R6e — Regenerate changed subset with soft_9_8

Mục tiêu:

* Chỉ regenerate 216 câu bị thay đổi selected_articles.
* Merge lại với base answer P6.R4.

Kết quả:

```text
changed_count: 216
processed: 216
missing: 0
```

Sau error analysis:

```text
total_questions: 2000
low_confidence_count: 276
unsupported_citation_count: 0
legacy_or_unknown_law_id: 221
answer_maybe_truncated: 48
answer_insufficient_basis: 17
too_many_selected_articles: 0
```

Quality check:

```text
rows: 2000
unique_ids: 2000
duplicate_ids: 0
empty_answer: 0
think_tag_count: 0
```

Trạng thái:

```text
P6.R6e — VERIFIED
```

Ý nghĩa:

* `too_many_selected_articles` đã về 0.
* Low confidence giảm mạnh từ 454 xuống 276.
* Còn lỗi truncation và metadata legacy.

---

## P6.R6f — Truncated answer subset fix

Mục tiêu:

* Regenerate các answer bị `answer_maybe_truncated`.
* Sau đó patch thêm các case false-positive/truncated heuristic.

Các bước chính:

1. Tạo danh sách 48 ID bị truncate.
2. Regenerate subset với context/token cao hơn.
3. Merge lại.
4. Rerun error analysis.
5. Patch thủ công các case còn bị flag do heuristic.

Kết quả final:

```text
total_questions: 2000
low_confidence_count: 237
unsupported_citation_count: 0
too_many_selected_articles: 0
answer_maybe_truncated: 0
legacy_or_unknown_law_id: 221
answer_insufficient_basis: 17
```

Best answer file sau P6.R6f:

```text
data/outputs/error_analysis_v2_p6r6f_truncated_fix/generated_answers_p6r6f_merged_fix_truncated_final.jsonl
```

Error analysis:

```text
data/outputs/error_analysis_v2_p6r6f_soft_9_8_final/
```

Trạng thái:

```text
P6.R6f — VERIFIED / FINAL ANSWER STABILITY
```

Ý nghĩa:

* Đưa truncation về 0.
* Giữ unsupported citation = 0.
* Phase 6 chuyển trọng tâm sang residual legacy metadata.

---

## P6.R7 — Residual legacy metadata inspection

Mục tiêu:

* Phân tích 221 case `legacy_or_unknown_law_id`.
* Xác định lỗi do answer, selected metadata, canonical metadata, hay heuristic false positive.

Kết quả:

```text
total_low_confidence: 237
total_legacy_or_unknown_law_id: 221
unsupported_citation_count_current: 0
too_many_selected_articles_current: 0
answer_maybe_truncated_current: 0
answer_insufficient_basis_current: 17
```

Trigger chính:

```text
answer_mentions_khong_so: 180
selected_contains_khong_so: 218
selected_contains_old_code_or_legacy_doc: 216
version_overlap_suspected: 216
needs_canonical_metadata_cleanup: 218
needs_retrieval_filtering: 216
```

Recommended actions:

```text
answer_patch_possible: 180
canonical_metadata_cleanup_needed: 38
no_action_false_positive: 3
```

Output:

```text
data/outputs/error_analysis_v2_p6r7_legacy_metadata_residual/
```

Trạng thái:

```text
P6.R7 — VERIFIED
```

Ý nghĩa:

* Residual không phải unsupported citation.
* Có 2 lớp vấn đề:

  * answer display có “Không số”
  * selected/canonical metadata chứa “Không số” hoặc legacy overlap

---

## P6.R8 — Targeted legacy answer display patch

Mục tiêu:

* Patch answer text cho các case `answer_patch_possible`.
* Chỉ xóa lỗi hiển thị `Không số`.
* Không sửa retrieval/canonical/selected articles.
* Không gọi LLM.

Kết quả:

```text
target_patch_ids: 180
patched_count: 172
before_contains_khong_so_count: 180
after_contains_khong_so_count: 144
non_target_changed_count: 0
```

Safety:

```text
row_count_is_2000: True
unique_id_count_is_2000: True
empty_answer_ids: []
think_marker_ids: []
legal_basis_lost_ids: []
only_target_ids_changed: True
```

Trạng thái:

```text
P6.R8 — SAFE RUNTIME COMPLETED / NEED R8a
```

Ý nghĩa:

* Patch an toàn nhưng chưa đủ mạnh.
* Nhiều `Không số` còn nằm trong block `Căn cứ pháp lý`.

---

## P6.R8a — Stronger target-only Khong so cleanup

Mục tiêu:

* Patch tiếp 144 answer còn `Không số` sau P6.R8.
* Chỉ áp dụng target-only.
* Làm sạch pattern trong legal basis line:

  * `Điều X - Không số - Tên văn bản`
  * `Pháp lệnh Không số`
  * `Luật ... và Không số`
  * `Ban Ghi Nho Không số`

Kết quả runtime:

```text
target_patch_ids: 144
patched_count: 143
before_contains_khong_so_count: 144
after_contains_khong_so_count: 4
non_target_changed_count: 0
```

Rerun error analysis:

```text
total_questions: 2000
low_confidence_count: 237
unsupported_citation_count: 0
```

Rerun residual diagnostic:

```text
answer_mentions_khong_so: 4
needs_answer_patch: 4
canonical_metadata_cleanup_needed: 214
selected_contains_khong_so: 218
needs_canonical_metadata_cleanup: 218
needs_retrieval_filtering: 216
```

Best answer file sau P6.R8a:

```text
data/outputs/error_analysis_v2_p6r8a_legacy_answer_patch_stronger/generated_answers_p6r8a_legacy_display_patch.jsonl
```

Trạng thái:

```text
P6.R8a — VERIFIED
```

Ý nghĩa:

* Answer display issue gần như đã xử lý xong.
* Residual còn lại chủ yếu là canonical/retrieval metadata, không phải answer.

---

## P6.R9 — Canonical legacy metadata cleanup planning

Mục tiêu:

* Phân tích phần residual metadata sau P6.R8a.
* Không sửa canonical ngay.
* Lập kế hoạch cleanup/alias/retrieval filtering an toàn.

Kết quả sau fix filter bug:

```text
status: completed
input_residual_report_rows: 221
filtered_residual_rows: 221
total_selected_article_refs_scanned: 1532
unique_selected_article_ids: 1114
canonical_join_missing_count: 0
grouped_article_rows: 1114
grouped_law_rows: 448
```

Anomaly chính:

```text
status_missing_or_unknown: 1532
modern_and_legacy_overlap_same_question: 806
law_title_trailing_so: 786
law_title_duplicate_law_type_or_law_id: 564
law_id_khong_so: 264
law_title_contains_khong_so: 264
law_title_suspicious_normalization: 264
old_code_or_legacy_doc: 231
```

Recommended actions:

```text
canonical_metadata_cleanup_candidate: 664
manual_review_required: 616
retrieval_filter_candidate: 189
exact_alias_mapping_candidate: 63
```

Top affected families:

```text
Bộ luật Lao động: 293
Luật Thương mại: 221
Bộ luật Dân sự: 186
Nghị định xử phạt lao động: 61
Nghị định/Thông tư thuế: 50
Luật Doanh nghiệp: 41
Luật Sở hữu trí tuệ: 33
Luật Quản lý thuế: 27
```

Output:

```text
data/outputs/error_analysis_v2_p6r9_canonical_legacy_cleanup_plan/
```

Các file chính:

```text
canonical_legacy_metadata_report.csv
canonical_legacy_grouped_by_article.csv
canonical_legacy_grouped_by_law.csv
canonical_legacy_cleanup_summary.json
canonical_legacy_cleanup_plan.md
candidate_retrieval_filter_rules.json
candidate_metadata_cleanup_rules.json
```

Trạng thái:

```text
P6.R9 — VERIFIED
```

Ý nghĩa:

* Không mất canonical join.
* Vấn đề là metadata canonical hiện có `Không số`, title normalization chưa sạch và overlap giữa văn bản cũ/mới.
* Chưa nên sửa trực tiếp `legal_articles.parquet`.
* Nên ưu tiên display-only cleanup / alias planning / retrieval filtering ở nhánh riêng.

---

## 4. Kết quả cuối Phase 6

Best retrieval hiện tại:

```text
data/outputs/error_analysis_v2_p6r6d_selector_tuning_threshold_aligned/config_soft_9_8/retrieval_results_p6r6_tightened.jsonl
```

Best answer hiện tại:

```text
data/outputs/error_analysis_v2_p6r8a_legacy_answer_patch_stronger/generated_answers_p6r8a_legacy_display_patch.jsonl
```

Error analysis tương ứng:

```text
data/outputs/error_analysis_v2_p6r8a_legacy_answer_patch_error_analysis/
```

P6.R9 cleanup planning:

```text
data/outputs/error_analysis_v2_p6r9_canonical_legacy_cleanup_plan/
```

Final metrics:

```text
total_questions: 2000
low_confidence_count: 237
unsupported_citation_count: 0
too_many_selected_articles: 0
answer_maybe_truncated: 0
answer_insufficient_basis: 17
legacy_or_unknown_law_id: 221
answer_mentions_khong_so: 4
selected_contains_khong_so: 218
```

So với P6.R4:

```text
low_confidence_count: 454 -> 237
too_many_selected_articles: 216 -> 0
answer_maybe_truncated: 52 -> 0
unsupported_citation_count: 0 -> 0
```

---

## 5. Các quyết định kỹ thuật quan trọng

## 5.1. Không tiếp tục patch answer sau P6.R8a

Lý do:

* `answer_mentions_khong_so` đã giảm từ 180 xuống 4.
* Residual lớn nhất hiện là `selected_contains_khong_so` và canonical metadata.
* Patch answer tiếp không xử lý được gốc lỗi.

Quyết định:

```text
Stop answer display patching after P6.R8a.
```

---

## 5.2. Không sửa trực tiếp canonical corpus trong Phase 6

Lý do:

* Có 616 case `manual_review_required`.
* Có 63 case chỉ là alias mapping candidate, chưa đủ chắc để tự động map.
* Sửa trực tiếp `legal_articles.parquet` có thể làm sai citation hoặc mất traceability.

Quyết định:

```text
Do not modify legal_articles.parquet in Phase 6.
```

---

## 5.3. Metadata cleanup nên là nhánh riêng

Các hướng cleanup đề xuất:

1. Display-only canonical metadata cleanup layer.
2. Retrieval-time legacy filter.
3. Exact alias mapping.
4. Full canonical corpus repair/rebuild nếu có nguồn chuẩn hơn.

Quyết định:

```text
Treat metadata cleanup as a separate post-Phase-6 branch.
```

---

## 5.4. Phase 7 không dùng để chữa metadata

Phase 7 nên tập trung vào:

* reranking
* LLM verifier
* giảm `answer_insufficient_basis`
* kiểm tra selected_articles trước khi generation

Không nên dùng Phase 7 để:

* sửa `Không số`
* sửa canonical law_id/law_title
* map văn bản cũ sang văn bản mới nếu chưa có rule chắc chắn

Quyết định:

```text
Phase 7 should not mask canonical metadata issues.
```

---

## 6. Trạng thái tổng thể Phase 6

```text
P6.T1  — VERIFIED
P6.T2  — VERIFIED
P6.R1  — VERIFIED
P6.R2  — VERIFIED
P6.R3  — DONE / IMPROVED BY R3.1-R3.2
P6.R4  — VERIFIED
P6.R5  — VERIFIED
P6.R5b — VERIFIED
P6.R6a — VERIFIED
P6.R6b — VERIFIED / NOT FINAL CONFIG
P6.R6c — COMPLETED / NOT FINAL
P6.R6d — VERIFIED
P6.R6e — VERIFIED
P6.R6f — VERIFIED / FINAL ANSWER STABILITY
P6.R7  — VERIFIED
P6.R8  — SAFE COMPLETED / SUPERSEDED BY R8a
P6.R8a — VERIFIED
P6.R9  — VERIFIED
```

Final Phase 6 status:

```text
Phase 6 — COMPLETED / READY FOR PHASE 7
```

---

## 7. Handoff sang Phase 7

Input nên dùng cho Phase 7:

```text
Retrieval:
data/outputs/error_analysis_v2_p6r6d_selector_tuning_threshold_aligned/config_soft_9_8/retrieval_results_p6r6_tightened.jsonl

Answers:
data/outputs/error_analysis_v2_p6r8a_legacy_answer_patch_stronger/generated_answers_p6r8a_legacy_display_patch.jsonl

Error analysis:
data/outputs/error_analysis_v2_p6r8a_legacy_answer_patch_error_analysis/

Metadata cleanup planning:
data/outputs/error_analysis_v2_p6r9_canonical_legacy_cleanup_plan/
```

Phase 7 nên tập trung vào:

* reranker interface
* rerank selected candidates trước article selection
* LLM verifier kiểm tra selected_articles có đủ căn cứ không
* giảm `answer_insufficient_basis`
* giảm noise trong selected_articles nhưng không làm mất recall

Không nên làm ngay trong Phase 7:

* sửa canonical `legal_articles.parquet`
* alias mapping tự động cho `Không số`
* lọc bỏ toàn bộ văn bản cũ nếu chưa có rule chắc chắn
* regenerate toàn bộ answer nếu chưa có thay đổi retrieval/selection đáng kể

---

## 8. Kết luận

Phase 6 đã hoàn thành vai trò đánh giá và hardening pipeline. Các lỗi nghiêm trọng về unsupported citation, too many selected articles và truncated answers đã được xử lý về 0. Low-confidence giảm đáng kể từ 454 xuống 237. Phần residual còn lại chủ yếu là metadata/canonical legacy, đã được phân tích và lập kế hoạch cleanup nhưng chưa nên sửa trực tiếp trong Phase 6.

Pipeline hiện đã đủ điều kiện chuyển sang Phase 7 với baseline sạch hơn và có đầy đủ diagnostic artifacts để kiểm soát rủi ro.


---
# Phase 7 — Reranker / LLM Verifier

## P7.T1 — Reranker interface

### Codex Prompt

Dùng prompt: `P7.T1`.

### Deliverables

```text
backend/retrieval/reranker.py
```

### Acceptance Criteria

```text
[ ] Có base interface rerank(question, candidates).
[ ] Có no-op reranker fallback.
[ ] Không phá baseline retrieval.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.reranker import NoOpReranker
print(NoOpReranker().rerank("q", []))
PY
```

---

## P7.T2 — LLM verifier

### Codex Prompt

Dùng prompt: `P7.T2`.

### Deliverables

```text
backend/retrieval/llm_verifier.py
backend/prompts/verifier_prompt.txt
```

### Acceptance Criteria

```text
[ ] Verifier output JSON parse được.
[ ] Có fallback khi JSON lỗi.
[ ] Không dùng verifier nếu chưa bật config.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.llm_verifier import LLMVerifier
print("verifier import ok")
PY
```

---

# Phase 8 — Neo4j Graph Expansion

## P8.T1 — Neo4j client

### Codex Prompt

Dùng prompt: `P8.T1`.

### Deliverables

```text
backend/infrastructure/graph_store/neo4j_client.py
```

### Acceptance Criteria

```text
[ ] Có health_check().
[ ] Có run_read_query().
[ ] Có run_write_query().
[ ] Không connect ở import-time.
```

### User-run commands

```bash
python - <<'PY'
from backend.infrastructure.graph_store.neo4j_client import Neo4jClient
print("neo4j client import ok")
PY
```

---

## P8.T2 — Build graph index

### Codex Prompt

Dùng prompt: `P8.T2`.

### Deliverables

```text
backend/indexing/build_graph_index.py
```

### Acceptance Criteria

```text
[ ] Tạo Law nodes.
[ ] Tạo Article nodes.
[ ] Tạo HAS_ARTICLE relationships.
[ ] Tạo PhapdienArticle nodes nếu có mapping.
[ ] Tạo DERIVED_FROM relationships.
[ ] Có constraints Cypher.
```

### User-run commands

```bash
python - <<'PY'
from backend.indexing.build_graph_index import build_graph_index
print("graph builder import ok")
PY
```

---

## P8.T3 — Graph expander

### Codex Prompt

Dùng prompt: `P8.T3`.

### Deliverables

```text
backend/retrieval/graph_expander.py
```

### Acceptance Criteria

```text
[ ] Input candidate_article_ids.
[ ] Return neighbor_article_ids + graph_boost_scores.
[ ] Không add neighbor mù quáng.
[ ] Có max_neighbors config.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.graph_expander import GraphExpander
print("graph expander import ok")
PY
```

---

# Phase 9 — Fine-tuning Preparation

## P9.T1 — Reranker training data builder

### Codex Prompt

Dùng prompt: `P9.T1`.

### Deliverables

```text
backend/evaluation/build_reranker_training_data.py
```

### Acceptance Criteria

```text
[ ] Output query, positive_article_id, hard_negative_article_ids.
[ ] Hard negatives lấy từ retrieval logs.
[ ] Không fine-tune model trong task này.
[ ] Có validation article_id tồn tại trong legal_articles.
```

### User-run commands

```bash
python - <<'PY'
from backend.evaluation.build_reranker_training_data import build_reranker_training_data
print("training data builder import ok")
PY
```

---

# Utility Tasks

## U1 — End-to-end baseline runner

### Codex Prompt

Dùng prompt: `U1`.

### Deliverables

```text
scripts/run_phase_1_to_5_baseline.py
```

### Acceptance Criteria

```text
[ ] Script gọi lần lượt Phase 1 → Phase 5.
[ ] Có logging start/end mỗi step.
[ ] Stop on failure.
[ ] Không duplicate business logic.
[ ] Người dùng tự chạy.
```

### User-run commands

```bash
python scripts/run_phase_1_to_5_baseline.py
```

---

## U2 — Debug retrieval for one question

### Codex Prompt

Dùng prompt: `U2`.

### Deliverables

```text
scripts/debug_retrieval_for_question.py
```

### Acceptance Criteria

```text
[ ] Có arg --id.
[ ] In question/domain/answer_type/complexity.
[ ] In BM25 hits.
[ ] In dense hits.
[ ] In exact hits.
[ ] In phapdien hits và mapped articles.
[ ] In RRF merged candidates.
[ ] In selected final articles.
[ ] Không generate answer.
```

### User-run commands

```bash
python scripts/debug_retrieval_for_question.py --id 1
```

---
## U4 — Precision-Oriented Citation Pruning

### 1. Mục tiêu

Điểm hiện tại cho thấy hệ thống đang bị **precision thấp**, trong khi recall không quá thấp:

```json
{
  "ARTICLES_F2MACRO": 0.3594,
  "DOCS_F2MACRO": 0.4496,
  "ARTICLES_PRECISION": 0.1544,
  "ARTICLES_RECALL": 0.5973,
  "DOCS_PRECISION": 0.2051,
  "DOCS_RECALL": 0.71
}
```

Nhận định:

* Hệ thống đang trả về quá nhiều `relevant_docs` và `relevant_articles`.
* Recall tương đối ổn, nhưng precision thấp do nhiều citation nhiễu.
* Cần tối ưu theo hướng **giảm số căn cứ trả về**, ưu tiên căn cứ thực sự được dùng trong answer.

Mục tiêu của U4:

```text
Tăng ARTICLES_PRECISION và DOCS_PRECISION.
Giữ ARTICLES_RECALL và DOCS_RECALL không giảm quá mạnh.
Không sửa file final hiện tại.
Không gọi LLM/retrieval/index.
Chỉ post-process deterministic trên submission JSON.
```

---

### 2. File đầu vào và nguyên tắc an toàn

File đầu vào hiện tại:

```text
data/outputs/results_patched_final.json
```

Không ghi đè các file sau:

```text
data/outputs/results_patched_final.json
data/outputs/submission_final.zip
final_submission/submission.zip
```

Toàn bộ output U4 ghi vào:

```text
data/outputs/precision_pruning/
```

Các file output dự kiến:

```text
data/outputs/precision_pruning/results_pruned_a.json
data/outputs/precision_pruning/results_pruned_b.json
data/outputs/precision_pruning/results_pruned_c.json

data/outputs/precision_pruning/submission_pruned_a.zip
data/outputs/precision_pruning/submission_pruned_b.zip
data/outputs/precision_pruning/submission_pruned_c.zip

data/outputs/precision_pruning/prune_report_a.json
data/outputs/precision_pruning/prune_report_b.json
data/outputs/precision_pruning/prune_report_c.json

data/outputs/precision_pruning/prune_changes_a.jsonl
data/outputs/precision_pruning/prune_changes_b.jsonl
data/outputs/precision_pruning/prune_changes_c.jsonl
```

---

### 3. U4.1 — Audit precision-risk

#### 3.1. Script cần tạo

```text
scripts/audit_submission_precision.py
```

#### 3.2. Input

```text
--input data/outputs/results_patched_final.json
--output-dir data/outputs/precision_pruning
```

#### 3.3. Output

```text
data/outputs/precision_pruning/audit_precision_summary.json
data/outputs/precision_pruning/audit_precision_by_record.csv
data/outputs/precision_pruning/top_risky_precision_records.csv
```

#### 3.4. Chỉ số cần audit

Với mỗi record cần tính:

```text
docs_count
articles_count
docs_gt_3
articles_gt_4
docs_gt_5
articles_gt_5
local_docs_count
answer_legal_basis_lines_count
articles_mentioned_in_answer_count
articles_not_mentioned_in_answer_count
tax_law_2006_2019_conflict
bidding_law_2013_2023_conflict
sme_decree_2018_2021_conflict
labor_penalty_2013_2022_conflict
```

Trong đó:

```text
local_docs_count = số lượng văn bản loại NQ-HĐND hoặc QĐ-UBND
```

Các conflict group:

```text
78/2006/QH11  vs 38/2019/QH14
43/2013/QH13  vs 22/2023/QH15
39/2018/NĐ-CP vs 80/2021/NĐ-CP
95/2013/NĐ-CP vs 12/2022/NĐ-CP
```

#### 3.5. Command chạy audit

```bash
cd /media/data/minhht/aiguru_ltran/Legal_Graph_RAG

mkdir -p data/outputs/precision_pruning

python scripts/audit_submission_precision.py \
  --input data/outputs/results_patched_final.json \
  --output-dir data/outputs/precision_pruning
```

---

### 4. U4.2 — Deterministic citation pruning

#### 4.1. Script cần tạo

```text
scripts/prune_submission_citations.py
```

#### 4.2. Input arguments

```text
--input
--output
--report
--changes
--zip-output
--variant {a,b,c}
```

Ví dụ:

```bash
python scripts/prune_submission_citations.py \
  --input data/outputs/results_patched_final.json \
  --output data/outputs/precision_pruning/results_pruned_a.json \
  --report data/outputs/precision_pruning/prune_report_a.json \
  --changes data/outputs/precision_pruning/prune_changes_a.jsonl \
  --zip-output data/outputs/precision_pruning/submission_pruned_a.zip \
  --variant a
```

#### 4.3. Nguyên tắc pruning

Giữ nguyên:

```text
id
question
answer
record order
total record count
```

Chỉ prune:

```text
relevant_docs
relevant_articles
```

Không được để rỗng:

```text
len(relevant_docs) >= 1
len(relevant_articles) >= 1
```

Nếu pruning làm rỗng citation thì rollback record đó và ghi warning.

---

### 5. Logic prune chi tiết

#### Rule 1 — Deduplicate

Deduplicate `relevant_docs` và `relevant_articles` nhưng giữ nguyên thứ tự ban đầu.

---

#### Rule 2 — Rebuild docs từ articles

Sau khi prune `relevant_articles`, rebuild lại `relevant_docs` từ các article còn lại.

Ví dụ:

```text
38/2019/QH14|Luật 38/2019/QH14 Luật Quản lý thuế số|Điều 59
```

thì doc tương ứng là:

```text
38/2019/QH14|Luật 38/2019/QH14 Luật Quản lý thuế số
```

Không giữ `relevant_docs` không còn article tương ứng.

---

#### Rule 3 — Ưu tiên article được nhắc trong answer

Tính điểm cao cho article nếu:

```text
law_id xuất hiện trong answer
article_no xuất hiện trong answer
cả law_id và article_no cùng xuất hiện trong answer
```

Gợi ý scoring:

```text
+100 nếu law_id xuất hiện trong answer
+80 nếu article_no xuất hiện trong answer
+60 nếu cả law_id và article_no xuất hiện trong answer
+30 nếu law_id xuất hiện trong question
+20 nếu law title keyword overlap với question/answer
```

---

#### Rule 4 — Hạn chế văn bản địa phương

Hạ điểm hoặc loại:

```text
NQ-HĐND
QĐ-UBND
```

nếu question không có địa danh/tỉnh/thành hoặc indicator địa phương.

Gợi ý scoring:

```text
-40 cho NQ-HĐND hoặc QĐ-UBND nếu question không có province/city/local indicator
```

Chỉ giữ văn bản địa phương khi:

```text
question có tên tỉnh/thành
hoặc answer trực tiếp nhắc văn bản đó
```

---

#### Rule 5 — Ưu tiên văn bản mới hơn khi conflict

Conflict groups:

```text
["78/2006/QH11", "38/2019/QH14"]
["43/2013/QH13", "22/2023/QH15"]
["39/2018/NĐ-CP", "80/2021/NĐ-CP"]
["95/2013/NĐ-CP", "12/2022/NĐ-CP"]
```

Rule:

```text
Nếu cả văn bản cũ và mới cùng xuất hiện:
- Ưu tiên giữ văn bản mới.
- Chỉ giữ văn bản cũ nếu answer trực tiếp nhắc văn bản cũ.
```

Gợi ý scoring:

```text
-50 cho old law nếu newer law cùng conflict group xuất hiện và old law không được nhắc trong answer
```

---

#### Rule 6 — Cap citation theo loại câu hỏi

##### 6.1. single_fact

Dấu hiệu:

```text
bao lâu
mấy ngày
tỷ lệ
mức phạt
thời hạn
điều kiện gì
ai bị xử phạt
```

Cap variant A:

```text
max_docs = 2
max_articles = 3
```

Cap variant B:

```text
max_docs = 1
max_articles = 2
```

Cap variant C:

```text
same as variant A
```

---

##### 6.2. list_policy

Dấu hiệu:

```text
những gì
những nội dung gì
những chính sách nào
bao gồm
các trường hợp
```

Cap variant A:

```text
max_docs = 4
max_articles = 5
```

Cap variant B:

```text
max_docs = 3
max_articles = 4
```

Cap variant C:

```text
same as variant A
```

---

##### 6.3. default

Cap variant A:

```text
max_docs = 3
max_articles = 4
```

Cap variant B:

```text
max_docs = 2
max_articles = 3
```

Cap variant C:

```text
same as variant A
```

---

# 6. Ba biến thể pruning

## Variant A — Balanced

Mục tiêu: tăng precision nhưng hạn chế mất recall.

```text
single_fact: max_docs=2, max_articles=3
list_policy: max_docs=4, max_articles=5
default: max_docs=3, max_articles=4
```

Output:

```text
results_pruned_a.json
submission_pruned_a.zip
```

Ưu tiên submit thử đầu tiên.

---

## Variant B — Aggressive precision

Mục tiêu: tăng precision mạnh hơn, chấp nhận recall giảm.

```text
single_fact: max_docs=1, max_articles=2
list_policy: max_docs=3, max_articles=4
default: max_docs=2, max_articles=3
```

Output:

```text
results_pruned_b.json
submission_pruned_b.zip
```

Chỉ submit nếu A vẫn precision thấp.

---

## Variant C — Answer-evidence only

Mục tiêu: chỉ giữ citation được answer thật sự dùng.

Logic:

```text
Ưu tiên giữ articles được nhắc trong answer.
Nếu không còn article nào, backfill từ highest scoring original articles.
Caps giống Variant A.
```

Output:

```text
results_pruned_c.json
submission_pruned_c.zip
```

Submit sau A nếu cần.

---

# 7. U4.3 — Validate submission JSON

## 7.1. Script cần tạo

```text
scripts/validate_submission_json.py
```

## 7.2. Input

```text
--input data/outputs/precision_pruning/results_pruned_a.json
```

## 7.3. Kiểm tra cần có

```text
records
unique_ids
empty_answer
empty_docs
empty_articles
khong_so_refs_records
disclaimer_records
internal_leakage_records
schema ok
```

Exit non-zero nếu lỗi schema fatal.

Expected output:

```text
records: 2000
unique_ids: 2000
empty_answer: 0
empty_docs: 0
empty_articles: 0
khong_so_refs_records: 0
disclaimer_records: 0
internal_leakage_records: 0
schema ok
```

---

# 8. Tests

## File test cần tạo

```text
tests/test_prune_submission_citations.py
```

## Test cases cần có

```text
test_parse_article_ref
test_deduplicate_preserve_order
test_rebuild_docs_from_articles
test_local_document_penalty
test_old_new_conflict_penalty
test_question_type_single_fact
test_question_type_list_policy
test_variant_a_caps
test_variant_b_caps
test_variant_c_answer_evidence
test_rollback_when_empty_refs
test_zip_contains_single_results_json
```

Chạy test:

```bash
pytest -q tests/test_prune_submission_citations.py
```

---

# 10. Commands chạy sau khi Codex implement

## 10.1. Chạy test

```bash
cd /media/data/minhht/aiguru_ltran/Legal_Graph_RAG

pytest -q tests/test_prune_submission_citations.py
```

---

## 10.2. Chạy audit

```bash
mkdir -p data/outputs/precision_pruning

python scripts/audit_submission_precision.py \
  --input data/outputs/results_patched_final.json \
  --output-dir data/outputs/precision_pruning
```

---

## 10.3. Chạy Variant A

```bash
python scripts/prune_submission_citations.py \
  --input data/outputs/results_patched_final.json \
  --output data/outputs/precision_pruning/results_pruned_a.json \
  --report data/outputs/precision_pruning/prune_report_a.json \
  --changes data/outputs/precision_pruning/prune_changes_a.jsonl \
  --zip-output data/outputs/precision_pruning/submission_pruned_a.zip \
  --variant a

python scripts/validate_submission_json.py \
  --input data/outputs/precision_pruning/results_pruned_a.json

unzip -l data/outputs/precision_pruning/submission_pruned_a.zip
```

---

## 10.4. Chạy Variant B

```bash
python scripts/prune_submission_citations.py \
  --input data/outputs/results_patched_final.json \
  --output data/outputs/precision_pruning/results_pruned_b.json \
  --report data/outputs/precision_pruning/prune_report_b.json \
  --changes data/outputs/precision_pruning/prune_changes_b.jsonl \
  --zip-output data/outputs/precision_pruning/submission_pruned_b.zip \
  --variant b

python scripts/validate_submission_json.py \
  --input data/outputs/precision_pruning/results_pruned_b.json

unzip -l data/outputs/precision_pruning/submission_pruned_b.zip
```

---

## 10.5. Chạy Variant C

```bash
python scripts/prune_submission_citations.py \
  --input data/outputs/results_patched_final.json \
  --output data/outputs/precision_pruning/results_pruned_c.json \
  --report data/outputs/precision_pruning/prune_report_c.json \
  --changes data/outputs/precision_pruning/prune_changes_c.jsonl \
  --zip-output data/outputs/precision_pruning/submission_pruned_c.zip \
  --variant c

python scripts/validate_submission_json.py \
  --input data/outputs/precision_pruning/results_pruned_c.json

unzip -l data/outputs/precision_pruning/submission_pruned_c.zip
```

---

# 11. Thứ tự submit thử

Nếu hệ thống giới hạn lượt submit, ưu tiên:

```text
1. data/outputs/precision_pruning/submission_pruned_a.zip
2. data/outputs/precision_pruning/submission_pruned_c.zip
3. data/outputs/precision_pruning/submission_pruned_b.zip
```

Không submit Variant B đầu tiên vì aggressive quá, có thể làm recall giảm mạnh.

---

# 12. Kỳ vọng điểm sau pruning

Hiện tại:

```text
ARTICLES_PRECISION = 0.1544
ARTICLES_RECALL    = 0.5973
DOCS_PRECISION     = 0.2051
DOCS_RECALL        = 0.7100
```

Kỳ vọng Variant A:

```text
ARTICLES_PRECISION: 0.1544 -> 0.30 đến 0.45
DOCS_PRECISION:     0.2051 -> 0.35 đến 0.55
ARTICLES_RECALL:    giảm nhẹ hoặc vừa
DOCS_RECALL:        giảm nhẹ hoặc vừa
```

Nếu Variant A tăng precision nhưng F2 giảm ít hoặc tăng, lấy A làm baseline mới.

Nếu A chưa đủ precision, thử Variant C.

Nếu C vẫn thấp, thử Variant B.

---

# 13. Kết luận

U4 không nhằm cải thiện answer generation mà nhằm cải thiện **citation precision**.

Chiến lược chính:

```text
Ít căn cứ hơn.
Đúng căn cứ hơn.
Chỉ giữ căn cứ answer thật sự dùng.
Loại văn bản nhiễu, văn bản địa phương không cần thiết, văn bản cũ khi có văn bản mới.
```

Output chính cần quan tâm đầu tiên:

```text
data/outputs/precision_pruning/submission_pruned_a.zip
```

---

# Definition of Done chung

Một task chỉ được coi là xong khi:

```text
[ ] Deliverables đã tạo/sửa đúng file.
[ ] Acceptance Criteria được Codex checklist lại.
[ ] Có lệnh test/validation để người dùng chạy.
[ ] Không có logic vượt scope task.
[ ] Không hard-code path.
[ ] Không tự chạy lệnh thay người dùng.
[ ] Nếu có test, pytest tương ứng pass khi người dùng chạy.
```
## Workflow vận hành từ Phase 3 trở đi

- Môi trường code chính: máy Windows local.
- Môi trường chạy nặng: GX10.
- Codex thực hiện code/edit/test unit nhẹ trên Windows; người dùng tự chạy các lệnh validate nặng trên GX10 và gửi log lại.
- Quy trình khuyến nghị:
  1. Code trên Windows.
  2. Chạy unit test nhẹ trên Windows nếu phù hợp.
  3. Commit/push lên branch làm việc.
  4. GX10 `git pull`.
  5. GX10 chạy smoke/full validation với dữ liệu và index thật.
- Không commit generated artifacts từ GX10:
  - `data/processed/exact_index.duckdb`
  - `data/processed/exact_index.json`
  - Qdrant/OpenSearch volumes/data
  - cache, logs, temporary outputs
- Dense/vector jobs trên GX10 nên chạy trong NVIDIA PyTorch container. BM25 và exact DuckDB có thể chạy ngoài container nếu dependency đầy đủ.
- Phase 3+ phải tách rõ code change và runtime validation: báo cáo cuối cần ghi lệnh GX10 cần chạy, expected output, và trạng thái pass/fail dựa trên log người dùng cung cấp.

