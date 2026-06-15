# CONTEXT.md — Legal Graph RAG Competition Project

## 0. Mục tiêu tài liệu

File này dùng làm **project context cho Codex/Coding Agent** khi phát triển repo `Legal_Graph_RAG`.

Mục tiêu của project là xây dựng hệ thống **Vietnamese Legal RAG / Legal Article Retrieval & QA** cho cuộc thi truy hồi và hỏi đáp văn bản pháp luật tiếng Việt.

Hệ thống cần nhận đầu vào là danh sách câu hỏi pháp lý tiếng Việt:

```json
[
  {
    "id": 1,
    "question": "..."
  }
]
```

và tạo file nộp bài `results.json` đúng format:

```json
[
  {
    "id": 1,
    "question": "...",
    "answer": "...",
    "relevant_docs": [
      "<mã văn bản>|<tên văn bản>"
    ],
    "relevant_articles": [
      "<mã văn bản>|<tên văn bản>|<Điều X>"
    ]
  }
]
```

Nguyên tắc quan trọng nhất:

> **LLM không được tự quyết định `relevant_docs` và `relevant_articles`. Hai trường này phải được sinh bằng code từ canonical `legal_articles` registry. LLM chỉ diễn giải câu trả lời dựa trên các điều luật đã chọn.**

---

## 1. Bối cảnh bài toán

Cuộc thi yêu cầu xây dựng hệ thống AI hỗ trợ doanh nghiệp SME tại Việt Nam tra cứu và hỏi đáp pháp lý.

Các nhiệm vụ chính:

1. **Legal Information Retrieval**
   - Tìm đúng văn bản pháp luật.
   - Tìm đúng điều luật liên quan.
   - Output đúng format `law_id|law_title|Điều X`.

2. **Legal Question Answering**
   - Trả lời câu hỏi pháp lý bằng tiếng Việt.
   - Dựa trên điều luật đã retrieve.
   - Có dẫn nguồn rõ ràng.
   - Không bịa điều luật.
   - Có cảnh báo giới hạn tư vấn AI.

3. **Submission**
   - Tạo duy nhất file `results.json`.
   - Zip phẳng thành `submission.zip`.
   - `results.json` phải nằm ngay ở gốc zip, không nằm trong thư mục con.

---

## 2. Đặc điểm testset

Testset đã upload vào project dưới tên:

```text
data/raw/R2AIStage1DATA.json
```

Nội dung là list JSON gồm khoảng **2.000 câu hỏi**, mỗi item có:

```json
{
  "id": 1,
  "question": "..."
}
```

Các nhóm chủ đề chính trong testset:

```text
1. Hỗ trợ doanh nghiệp nhỏ và vừa
2. Thuế, hóa đơn, chứng từ, xử phạt thuế
3. Lao động, BHXH, công đoàn, an toàn vệ sinh lao động
4. Kế toán, báo cáo tài chính, tài khoản kế toán
5. Sở hữu trí tuệ, quyền tác giả, nhãn hiệu, kiểu dáng, giống cây trồng
6. Đăng ký doanh nghiệp, hộ kinh doanh, chủ sở hữu hưởng lợi
7. Thương mại, hợp đồng, đại lý, nhượng quyền, đấu thầu
8. Bảo lãnh tín dụng cho doanh nghiệp nhỏ và vừa
9. Bảo vệ người tiêu dùng, dữ liệu khách hàng
10. Một số câu long-tail: môi trường, PPP, trọng tài, dân sự, cạnh tranh, xây dựng...
```

Các kiểu câu hỏi phổ biến:

```text
- Hỏi điều kiện
- Hỏi hồ sơ/thủ tục
- Hỏi thời hạn
- Hỏi mức phạt/biện pháp khắc phục
- Hỏi nghĩa vụ/trách nhiệm
- Hỏi kế toán/hạch toán/tài khoản
- Hỏi yes/no: “có được không”, “có bị phạt không”
- Hỏi multi-hop: “vừa ... vừa ...”, “đồng thời ...”, “sau đó ...”
```

Vì vậy pipeline cần có:

```text
- domain routing
- answer type classification
- exact search mạnh cho số điều, thời hạn, tài khoản, mức phạt
- query decomposition cho câu multi-hop
- dynamic top-k để cân bằng Precision/Recall/F2
```

---

## 3. Dữ liệu dự kiến sử dụng

### 3.1. Dataset chính từ Hugging Face

1. `tmquan/phapdien-moj-gov-vn`
   - Vai trò: **retrieval source chính**.
   - Dữ liệu dạng điều pháp điển.
   - Có `topic_title`, `subject_title`, `chapter_title`, `article_title`, `content_text`, `source_note_text`, `related_note_text`, `source_url`.
   - Lưu ý: `article_title` trong Pháp điển không phải lúc nào cũng là `Điều X` của văn bản gốc.
   - Không dùng trực tiếp để sinh `relevant_articles`.
   - Cần map sang canonical `LegalArticle`.

2. `tmquan/anle-toaan-gov-vn`
   - Vai trò: **nguồn phụ trợ reasoning/tình huống**.
   - Không dùng làm nguồn chính để sinh `relevant_articles`.
   - Có thể dùng để:
     - giải thích tình huống,
     - query expansion,
     - hard negative mining,
     - bổ sung thực tiễn áp dụng.

3. `tmquan/vbpl-vn` hoặc nguồn VBPL tương đương
   - Vai trò: **canonical legal registry**.
   - Đây là nguồn quan trọng nhất để sinh:
     - `legal_documents.parquet`
     - `legal_articles.parquet`
     - `relevant_docs`
     - `relevant_articles`
     - citation trong answer.

### 3.2. Embedding model

Dùng:

```text
darklethelong/vnlegal-lal
```

Đặc điểm sử dụng:

```text
- Legal embedding model tiếng Việt.
- Output vector 1024 chiều.
- Query nên encode với instruction prefix:
  "Instruct: Given a Vietnamese legal question, retrieve relevant legal passages that answer the question\nQuery: "
- Document encode không cần prefix.
- Không trộn vector 1024-D của model này với vector 2048-D có sẵn từ dataset khác.
```

### 3.3. Generator LLM

Ưu tiên model open-weight, miễn phí, dưới 14B:

```text
- Qwen3-8B
- Qwen2.5-7B-Instruct
```

Chạy local bằng:

```text
- vLLM: dùng cho batch generation nghiêm túc
- Ollama: dùng cho baseline setup nhanh
```

Cấu hình generation:

```yaml
temperature: 0.0
do_sample: false
max_new_tokens: 700
```

---

## 4. Kiến trúc tổng thể

Pipeline cuối cùng nên triển khai theo phase.

### Phase 1 — Baseline retrieval không Neo4j

Mục tiêu: chạy end-to-end, sinh được `results.json`, retrieval đủ tốt.

```text
Test questions
↓
Query Analyzer
- domain router
- answer type classifier
- complexity detector
- legal entity extractor
↓
Hybrid Retrieval
- BM25 legal_articles
- Dense legal_articles bằng vnlegal-lal
- BM25 phapdien
- Dense phapdien bằng vnlegal-lal
- Exact search theo điều, luật, mã, tài khoản, thời hạn, mức phạt
↓
Map phapdien candidates → canonical legal_articles
↓
RRF Fusion
↓
Dynamic Article Selection
↓
Grounded QA Generation
↓
Citation Postprocess
↓
Submission Builder
```

### Phase 2 — Thêm Neo4j Graph Expansion

Neo4j **không thay thế** OpenSearch/Qdrant. Neo4j chỉ dùng để mở rộng quan hệ pháp lý.

```text
Hybrid retrieval top candidates
↓
Neo4j graph expansion
- same law neighbor articles
- related articles
- phapdien → VBPL mapping
- law guides/amends/replaces
- anle applies article
↓
Graph-aware scoring
↓
Rerank/select final articles
```

### Phase 3 — Reranker / LLM verifier

```text
Retrieve top 100–150
↓
Rerank top candidates
↓
LLM verifier top 20
↓
Select final articles
```

### Phase 4 — Fine-tuning

Chỉ fine-tune sau khi đã có baseline và log lỗi.

Ưu tiên:

```text
1. Fine-tune reranker
2. Fine-tune embedding nếu dense retrieval yếu
3. Fine-tune generator nếu answer diễn đạt kém
```

---

## 5. Tech stack

### Core

```text
Python 3.11+
Polars / Pandas
DuckDB
datasets
rapidfuzz
pydantic
PyYAML
```

### Search / Storage

```text
OpenSearch hoặc Elasticsearch:
- BM25
- exact phrase
- field boosting

Qdrant:
- vector search
- cosine similarity
- 1024-D vectors từ vnlegal-lal

PostgreSQL hoặc DuckDB:
- canonical registry
- processed data
- logs

Neo4j:
- dùng từ Phase 2
- legal knowledge graph
```

### ML / LLM

```text
transformers
torch
sentence-transformers nếu cần
vLLM
Ollama optional
```

### API/demo nếu cần

```text
FastAPI
Uvicorn
```

### Submission

```text
json
zipfile
custom validator
```

---

## 6. Cây thư mục mục tiêu

Repo hiện tại đã có cấu trúc khởi đầu. Nên phát triển thành cây sau:

```text
Legal_Graph_RAG/
├── backend/
│   ├── __init__.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── retrieval_config.yaml
│   │   ├── model_config.yaml
│   │   └── path_config.py
│   │
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   │
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── duckdb_client.py
│   │   │   ├── postgres_client.py
│   │   │   └── repositories.py
│   │   │
│   │   ├── vector_store/
│   │   │   ├── __init__.py
│   │   │   └── qdrant_client.py
│   │   │
│   │   ├── search_engine/
│   │   │   ├── __init__.py
│   │   │   └── opensearch_client.py
│   │   │
│   │   ├── graph_store/
│   │   │   ├── __init__.py
│   │   │   └── neo4j_client.py
│   │   │
│   │   ├── embedding_models/
│   │   │   ├── __init__.py
│   │   │   └── vnlegal_lal.py
│   │   │
│   │   └── gen_llm_models/
│   │       ├── __init__.py
│   │       ├── qwen_client.py
│   │       └── vllm_client.py
│   │
│   ├── schema/
│   │   ├── __init__.py
│   │   ├── legal_document.py
│   │   ├── legal_article.py
│   │   ├── phapdien_article.py
│   │   ├── anle_unit.py
│   │   ├── question.py
│   │   ├── retrieval_result.py
│   │   └── submission.py
│   │
│   ├── knowledge_processing/
│   │   ├── __init__.py
│   │   ├── hf_loader.py
│   │   ├── normalize_text.py
│   │   ├── load_testset.py
│   │   ├── load_phapdien.py
│   │   ├── load_anle.py
│   │   ├── load_vbpl.py
│   │   ├── extract_articles.py
│   │   ├── map_phapdien_to_vbpl.py
│   │   └── build_corpus.py
│   │
│   ├── indexing/
│   │   ├── __init__.py
│   │   ├── build_bm25_index.py
│   │   ├── build_vector_index.py
│   │   ├── build_graph_index.py
│   │   └── build_exact_index.py
│   │
│   ├── query_analysis/
│   │   ├── __init__.py
│   │   ├── domain_router.py
│   │   ├── answer_type_classifier.py
│   │   ├── complexity_detector.py
│   │   ├── legal_entity_extractor.py
│   │   └── query_decomposer.py
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── bm25_retriever.py
│   │   ├── dense_retriever.py
│   │   ├── exact_retriever.py
│   │   ├── phapdien_retriever.py
│   │   ├── graph_expander.py
│   │   ├── fusion.py
│   │   ├── reranker.py
│   │   ├── article_selector.py
│   │   └── hybrid_retrieval.py
│   │
│   ├── qa/
│   │   ├── __init__.py
│   │   ├── answer_generator.py
│   │   ├── citation_postprocess.py
│   │   └── answer_templates.py
│   │
│   ├── prompts/
│   │   ├── system_prompt.txt
│   │   ├── legal_qa_prompt.txt
│   │   ├── verifier_prompt.txt
│   │   └── query_decompose_prompt.txt
│   │
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── metrics.py
│   │   ├── pseudo_dev_builder.py
│   │   └── error_analysis.py
│   │
│   ├── submission/
│   │   ├── __init__.py
│   │   ├── build_results.py
│   │   ├── validate_results.py
│   │   └── make_zip.py
│   │
│   └── main.py
│
├── data/
│   ├── raw/
│   │   ├── R2AIStage1DATA.json
│   │   ├── phapdien/
│   │   ├── anle/
│   │   └── vbpl/
│   │
│   ├── processed/
│   │   ├── test_questions.parquet
│   │   ├── legal_documents.parquet
│   │   ├── legal_articles.parquet
│   │   ├── phapdien_articles.parquet
│   │   ├── phapdien_to_vbpl_map.parquet
│   │   ├── anle_units.parquet
│   │   └── test_questions_analyzed.parquet
│   │
│   └── outputs/
│       ├── results.json
│       └── submission.zip
│
├── scripts/
│   ├── 01_build_corpus.py
│   ├── 02_build_indexes.py
│   ├── 03_run_retrieval.py
│   ├── 04_generate_answers.py
│   ├── 05_build_submission.py
│   └── 06_validate_submission.py
│
├── notebooks/
│   ├── error_analysis.ipynb
│   └── retrieval_debug.ipynb
│
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 7. Phần load dữ liệu

### 7.1. Load flow

```text
Hugging Face datasets / raw JSON
↓
Raw loader
↓
Normalizer
↓
Canonical schema
↓
Processed parquet
↓
Indexing đọc parquet
```

Không index trực tiếp từ Hugging Face.

### 7.2. Output của load phase

```text
data/processed/
├── test_questions.parquet
├── legal_documents.parquet
├── legal_articles.parquet
├── phapdien_articles.parquet
├── anle_units.parquet
└── phapdien_to_vbpl_map.parquet
```

### 7.3. Nguyên tắc nguồn dữ liệu

```text
phapdien:
- dùng để tìm

vbpl/legal_articles:
- dùng để nộp
- nguồn duy nhất sinh relevant_articles/relevant_docs

anle:
- dùng để phụ trợ reasoning
- không dùng để nộp relevant_articles
```

---

## 8. Schema cốt lõi

### 8.1. LegalArticle

```python
from pydantic import BaseModel


class LegalArticle(BaseModel):
    article_id: str
    law_id: str
    law_title: str
    article_no: str
    article_title: str | None = None
    article_text: str
    source_url: str | None = None
    domain: str | None = None
    status: str | None = None

    @property
    def relevant_article_string(self) -> str:
        return f"{self.law_id}|{self.law_title}|{self.article_no}"

    @property
    def relevant_doc_string(self) -> str:
        return f"{self.law_id}|{self.law_title}"
```

### 8.2. TestQuestion

```python
from pydantic import BaseModel


class TestQuestion(BaseModel):
    id: int
    question: str
```

### 8.3. RetrievalCandidate

```python
from pydantic import BaseModel


class RetrievalCandidate(BaseModel):
    article_id: str
    source: str
    bm25_score: float = 0.0
    dense_score: float = 0.0
    exact_score: float = 0.0
    graph_score: float = 0.0
    rerank_score: float = 0.0
    final_score: float = 0.0
    metadata: dict = {}
```

### 8.4. SubmissionItem

```python
from pydantic import BaseModel


class SubmissionItem(BaseModel):
    id: int
    question: str
    answer: str
    relevant_docs: list[str]
    relevant_articles: list[str]
```

---

## 9. Domain router

Cần rule-based domain router trước.

```python
DOMAIN_KEYWORDS = {
    "sme_support": [
        "doanh nghiệp nhỏ và vừa", "DNNVV", "SME",
        "khởi nghiệp sáng tạo", "chuỗi giá trị",
        "cụm liên kết ngành", "khu làm việc chung",
        "ươm tạo", "hỗ trợ doanh nghiệp"
    ],
    "tax_invoice": [
        "thuế", "hóa đơn", "chứng từ", "biên lai",
        "mã số thuế", "khai thuế", "nộp thuế",
        "ấn định thuế", "cưỡng chế", "lệ phí môn bài"
    ],
    "labor_bhxh": [
        "lao động", "người lao động", "nhân viên",
        "hợp đồng lao động", "tiền lương", "thử việc",
        "làm thêm", "BHXH", "bảo hiểm xã hội",
        "công đoàn", "an toàn vệ sinh lao động"
    ],
    "accounting": [
        "kế toán", "báo cáo tài chính", "sổ kế toán",
        "chứng từ kế toán", "tài khoản", "hạch toán",
        "giá gốc", "nguyên giá", "dự phòng"
    ],
    "ip_consumer_data": [
        "sở hữu trí tuệ", "sở hữu công nghiệp", "nhãn hiệu",
        "sáng chế", "kiểu dáng", "quyền tác giả",
        "bản ghi âm", "bản ghi hình", "người tiêu dùng",
        "dữ liệu khách hàng", "bảo hành"
    ],
    "business_registration": [
        "đăng ký doanh nghiệp", "hộ kinh doanh",
        "giấy chứng nhận đăng ký", "cơ quan đăng ký kinh doanh",
        "người đại diện theo pháp luật", "vốn điều lệ",
        "chủ sở hữu hưởng lợi"
    ],
    "commerce_contract": [
        "hợp đồng", "thương mại", "đại lý", "nhượng quyền",
        "hội chợ", "triển lãm", "đấu thầu",
        "phạt vi phạm", "bồi thường", "giao hàng"
    ],
    "credit_guarantee": [
        "bảo lãnh tín dụng", "Quỹ bảo lãnh tín dụng",
        "chứng thư bảo lãnh", "bên bảo lãnh"
    ],
}
```

Domain chỉ dùng để boost, không filter cứng.

---

## 10. Answer type classifier

Cần detect các loại:

```text
deadline:
- "bao lâu", "thời hạn", "chậm nhất", "khi nào", "trong bao nhiêu ngày"

sanction:
- "bị phạt", "xử phạt", "khắc phục hậu quả", "phạt tiền"

procedure:
- "thủ tục", "đăng ký", "nộp", "gửi", "thực hiện như thế nào"

dossier:
- "hồ sơ", "giấy tờ", "tài liệu"

condition:
- "điều kiện", "đáp ứng", "trường hợp nào"

obligation:
- "nghĩa vụ", "trách nhiệm", "phải làm gì"

accounting:
- "tài khoản", "hạch toán", "ghi nhận", "sổ kế toán", "báo cáo tài chính"

yes_no:
- "có được", "có bị", "có phải", "được phép không"

multi_hop:
- "vừa", "đồng thời", "sau đó", "trong khi", "ngoài ra"
```

---

## 11. Retrieval configuration

Baseline balanced:

```yaml
retrieval:
  legal_bm25_top_k: 80
  legal_dense_top_k: 80
  phapdien_bm25_top_k: 50
  phapdien_dense_top_k: 50
  exact_top_k: 30
  fusion: rrf
  rrf_k: 60
  rerank_top_k: 100
  final_top_k_default: 7
```

Recall mode:

```yaml
retrieval:
  legal_bm25_top_k: 120
  legal_dense_top_k: 120
  phapdien_bm25_top_k: 80
  phapdien_dense_top_k: 80
  exact_top_k: 50
  rerank_top_k: 150
  final_top_k_default: 10
  multi_hop_max_articles: 14
```

Precision mode:

```yaml
retrieval:
  legal_bm25_top_k: 50
  legal_dense_top_k: 50
  phapdien_bm25_top_k: 30
  phapdien_dense_top_k: 30
  exact_top_k: 20
  rerank_top_k: 50
  final_top_k_default: 5
  multi_hop_max_articles: 8
```

---

## 12. Dynamic article selection

Chọn số điều theo answer type:

```python
def choose_max_articles(answer_type: str, complexity: str) -> int:
    if complexity == "multi_hop":
        return 12

    if answer_type in {"deadline", "amount", "accounting_account"}:
        return 4

    if answer_type in {"yes_no", "single_condition"}:
        return 5

    if answer_type in {"procedure", "dossier"}:
        return 7

    if answer_type == "sanction":
        return 6

    if answer_type in {"conditions", "obligations"}:
        return 8

    return 7
```

---

## 13. Fusion

Dùng Reciprocal Rank Fusion:

```python
def reciprocal_rank_fusion(result_lists: list[list[str]], k: int = 60):
    scores = {}

    for results in result_lists:
        for rank, doc_id in enumerate(results, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

Sau RRF, có thể cộng boost:

```text
+ exact law/article match
+ domain match
+ answer-type match
+ graph neighbor boost
```

---

## 14. QA generation

Prompt phải chặt:

```text
Bạn là trợ lý pháp lý AI cho doanh nghiệp tại Việt Nam.

Chỉ trả lời dựa trên CĂN CỨ PHÁP LÝ được cung cấp.
Không bịa văn bản, điều luật, khoản luật.
Phải nhắc rõ Điều X và tên văn bản tương ứng.
Nếu câu hỏi gồm nhiều ý, trả lời theo từng ý.

Câu hỏi:
{question}

Căn cứ pháp lý:
{selected_articles}

Yêu cầu trả lời:
- Kết luận trực tiếp trước.
- Sau đó nêu căn cứ theo từng Điều.
- Với câu hỏi xử phạt, phải nêu cả mức phạt và biện pháp khắc phục nếu có.
- Với câu hỏi hồ sơ, liệt kê thành phần hồ sơ.
- Với câu hỏi thời hạn, nêu rõ số ngày/tháng/năm và mốc tính.
- Kết thúc bằng lưu ý đây là tư vấn sơ bộ.
```

Postprocess bắt buộc:

```text
1. Check answer có chứa tất cả Điều X trong relevant_articles.
2. Nếu thiếu, thêm mục “Căn cứ pháp lý”.
3. Xóa citation không nằm trong selected_articles.
4. Chuẩn hóa “điều 4” → “Điều 4”.
5. Giới hạn answer không quá dài.
```

---

## 15. Submission builder

Không để LLM sinh `relevant_docs` / `relevant_articles`.

```python
def build_submission_item(question_item, answer: str, selected_articles: list[dict]):
    relevant_articles = []
    relevant_docs = set()

    for article in selected_articles:
        law_id = article["law_id"]
        law_title = article["law_title"]
        article_no = article["article_no"]

        relevant_docs.add(f"{law_id}|{law_title}")
        relevant_articles.append(f"{law_id}|{law_title}|{article_no}")

    return {
        "id": question_item["id"],
        "question": question_item["question"],
        "answer": answer,
        "relevant_docs": sorted(relevant_docs),
        "relevant_articles": relevant_articles,
    }
```

---

## 16. Validator

Validator cần check:

```text
[ ] File tên results.json
[ ] JSON là list
[ ] Mỗi item có id, question, answer, relevant_docs, relevant_articles
[ ] Không thiếu câu hỏi test
[ ] relevant_docs là list string
[ ] relevant_articles là list string
[ ] relevant_articles đúng format: law_id|law_title|Điều X
[ ] relevant_docs được suy ra từ relevant_articles
[ ] answer có chứa “Điều X” tương ứng
[ ] Không duplicate articles
[ ] Zip phẳng, không chứa folder con
```

---

## 17. Commands dự kiến

```bash
python scripts/01_build_corpus.py
python scripts/02_build_indexes.py
python scripts/03_run_retrieval.py
python scripts/04_generate_answers.py
python scripts/05_build_submission.py
python scripts/06_validate_submission.py
```

Hoặc CLI:

```bash
python -m backend.main build-corpus
python -m backend.main build-indexes
python -m backend.main run-retrieval
python -m backend.main generate-answers
python -m backend.main build-submission
```

---

## 18. Docker compose services

Phase 1:

```text
qdrant
opensearch
postgres hoặc duckdb local
```

Phase 2:

```text
neo4j
```

Có thể thêm:

```text
redis
```

nếu cần cache.

---

## 19. Coding conventions

Khi Codex viết code, tuân thủ:

```text
- Python 3.11+
- type hints đầy đủ
- docstring rõ ràng
- comment tiếng Việt cho logic quan trọng
- Pydantic cho schema
- không hard-code path quá nhiều, dùng config
- mỗi module chỉ làm một nhiệm vụ
- không nhét toàn bộ retrieval vào một file lớn
- không để LLM quyết định output format
- mọi output nộp bài phải qua validator
```

Ưu tiên clean code:

```text
- small functions
- explicit names
- logging rõ
- error handling tốt
- dễ debug từng phase
```

---

## 20. Các file nên code đầu tiên

Thứ tự ưu tiên để start:

```text
1. backend/schema/question.py
2. backend/schema/legal_article.py
3. backend/schema/submission.py
4. backend/knowledge_processing/normalize_text.py
5. backend/knowledge_processing/load_testset.py
6. backend/knowledge_processing/hf_loader.py
7. backend/knowledge_processing/load_phapdien.py
8. backend/knowledge_processing/load_vbpl.py
9. backend/knowledge_processing/extract_articles.py
10. scripts/01_build_corpus.py
```

Sau khi load phase chạy được, mới làm:

```text
11. infrastructure/vector_store/qdrant_client.py
12. infrastructure/search_engine/opensearch_client.py
13. infrastructure/embedding_models/vnlegal_lal.py
14. indexing/build_vector_index.py
15. indexing/build_bm25_index.py
16. retrieval/dense_retriever.py
17. retrieval/bm25_retriever.py
18. retrieval/fusion.py
19. retrieval/hybrid_retrieval.py
```

---

## 21. Nguyên tắc cuối cùng

```text
phapdien dùng để tìm.
vbpl/legal_articles dùng để nộp.
anle dùng để phụ trợ reasoning.
OpenSearch/Qdrant dùng để tìm candidate.
Neo4j dùng để mở rộng quan hệ.
Reranker/verifier dùng để chọn.
LLM dùng để diễn giải.
Submission builder dùng để xuất kết quả.
```

## Codex Skills

Before coding, read the relevant skill files in `skills/`.

For data ingestion tasks:
- read `skills/02_data_loading_huggingface.md`
- read `skills/03_legal_normalization.md`
- read `skills/04_canonical_article_registry.md`

For retrieval tasks:
- read `skills/05_embedding_vnlegal_lal.md`
- read `skills/06_hybrid_retrieval.md`
- read `skills/07_query_analysis.md`

For submission tasks:
- read `skills/08_submission_builder.md`

For graph tasks:
- read `skills/10_graph_expansion_neo4j.md`

Always follow:
- `skills/01_project_architecture.md`
- `skills/11_code_quality_testing.md`