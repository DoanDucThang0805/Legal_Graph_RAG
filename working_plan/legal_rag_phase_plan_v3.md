# Legal Graph RAG â€” Phase & Task Plan v3.1

> File liÃªn quan trá»±c tiáº¿p: `codex_task_prompts_vi_v3.md`  
> Báº£n cáº­p nháº­t: Phase 2 dÃ¹ng `legal_article_chunks.parquet` cho BM25/vector; Neo4j á»Ÿ Phase 8.  
> CÃ¡ch dÃ¹ng: má»Ÿ file prompt, chá»n Ä‘Ãºng `Task ID` tÆ°Æ¡ng á»©ng trong plan nÃ y, copy prompt cho Codex.  
> Quy táº¯c váº­n hÃ nh: **Codex chá»‰ sá»­a code vÃ  Ä‘á» xuáº¥t lá»‡nh kiá»ƒm thá»­; ngÆ°á»i dÃ¹ng lÃ  ngÆ°á»i cháº¡y lá»‡nh.**

---

## 0. NguyÃªn táº¯c kiá»ƒm soÃ¡t Codex

### 0.1. Quy táº¯c báº¯t buá»™c

1. Codex pháº£i Ä‘á»c `context.md`, `legal_rag_phase_plan_v3.md` vÃ  cÃ¡c skill liÃªn quan trÆ°á»›c khi code.
2. Codex chá»‰ Ä‘Æ°á»£c triá»ƒn khai Ä‘Ãºng `Task ID` Ä‘Æ°á»£c giao.
3. Codex khÃ´ng Ä‘Æ°á»£c tá»± má»Ÿ rá»™ng sang phase/task khÃ¡c.
4. Codex khÃ´ng Ä‘Æ°á»£c cháº¡y lá»‡nh build/test/index/generate trÃªn mÃ¡y ngÆ°á»i dÃ¹ng.
5. Codex pháº£i liá»‡t kÃª rÃµ cÃ¡c lá»‡nh Ä‘á»ƒ **ngÆ°á»i dÃ¹ng tá»± cháº¡y**.
6. Má»—i task pháº£i cÃ³:
   - Deliverables
   - Acceptance Criteria
   - Test/Validation Commands
   - Expected Outputs
   - Rollback/Debug note náº¿u phÃ¹ há»£p
7. Scripts chá»‰ lÃ  entrypoint má»ng; business logic pháº£i náº±m trong `backend/`.
8. KhÃ´ng hard-code path; dÃ¹ng config.
9. LLM khÃ´ng Ä‘Æ°á»£c tá»± sinh `relevant_docs` hoáº·c `relevant_articles`.
10. `relevant_docs` vÃ  `relevant_articles` chá»‰ Ä‘Æ°á»£c sinh tá»« canonical `legal_articles.parquet`.

### 0.2. Cáº¥u trÃºc lÃ m viá»‡c vá»›i Codex

Vá»›i má»—i task:

```text
1. NgÆ°á»i dÃ¹ng chá»n Task ID trong plan.
2. NgÆ°á»i dÃ¹ng copy prompt tÆ°Æ¡ng á»©ng tá»« codex_task_prompts_vi_v3.md.
3. Codex sá»­a/táº¡o code.
4. Codex tráº£ láº¡i:
   - File Ä‘Ã£ thay Ä‘á»•i
   - TÃ³m táº¯t thay Ä‘á»•i
   - Lá»‡nh ngÆ°á»i dÃ¹ng cáº§n cháº¡y
   - Acceptance Criteria checklist
5. NgÆ°á»i dÃ¹ng tá»± cháº¡y lá»‡nh.
6. Náº¿u lá»—i, dÃ¹ng prompt "FIX.TASK" trong codex_task_prompts_vi_v3.md.
```

### 0.3. Quy trÃ¬nh bÃ¡o cÃ¡o báº¯t buá»™c trÆ°á»›c/sau khi sá»­a code

## Quy trÃ¬nh bÃ¡o cÃ¡o báº¯t buá»™c trÆ°á»›c/sau khi sá»­a code

### TrÆ°á»›c khi sá»­a code

TrÆ°á»›c khi sá»­a báº¥t ká»³ file nÃ o, Codex pháº£i trÃ¬nh bÃ y ngáº¯n gá»n:

```text
Scope báº¡n hiá»ƒu:
- ...

Files dá»± kiáº¿n sá»­a:
- ...

Test command sáº½ cháº¡y / Ä‘á» xuáº¥t ngÆ°á»i dÃ¹ng cháº¡y:
- ...
```

Sau khi trÃ¬nh bÃ y pháº§n nÃ y, Codex pháº£i **dá»«ng láº¡i vÃ  chá» ngÆ°á»i dÃ¹ng xÃ¡c nháº­n** trÆ°á»›c khi sá»­a code, trá»« khi ngÆ°á»i dÃ¹ng Ä‘Ã£ ghi rÃµ: `triá»ƒn khai luÃ´n`.

### Sau khi hoÃ n thÃ nh

Sau khi sá»­a code xong, Codex pháº£i bÃ¡o cÃ¡o:

```text
Files changed:
- ...

Logic thay Ä‘á»•i:
- ...

Acceptance Criteria Ä‘Ã£ Ä‘áº¡t/chÆ°a Ä‘áº¡t:
- [x] ...
- [ ] ...

Test result:
- TÃ´i khÃ´ng tá»± cháº¡y lá»‡nh. NgÆ°á»i dÃ¹ng cáº§n cháº¡y:
  ...
- Náº¿u ngÆ°á»i dÃ¹ng Ä‘Ã£ cung cáº¥p log test, tÃ³m táº¯t káº¿t quáº£ táº¡i Ä‘Ã¢y.

Risk cÃ²n láº¡i:
- ...
```

Quy táº¯c quan trá»ng: **Codex khÃ´ng tá»± cháº¡y lá»‡nh thay ngÆ°á»i dÃ¹ng**. Codex chá»‰ Ä‘á» xuáº¥t lá»‡nh kiá»ƒm thá»­/validation Ä‘á»ƒ ngÆ°á»i dÃ¹ng tá»± cháº¡y.

---

## 1. Pipeline tá»•ng thá»ƒ

```text
R2AIStage1DATA.json
â†“
Phase 1: Data loading + canonical corpus
â†“
Phase 2: Indexing
  - OpenSearch / BM25
  - Qdrant / dense vector
  - Exact index
â†“
Phase 3: Query analysis
â†“
Phase 4: Hybrid retrieval baseline
â†“
Phase 5: QA generation + submission
â†“
Phase 6: Evaluation + error analysis
â†“
Phase 7: Reranker / LLM verifier
â†“
Phase 8: Neo4j graph expansion
â†“
Phase 9: Fine-tuning preparation
```

Baseline cáº§n hoÃ n thÃ nh trÆ°á»›c:

```text
Phase 0 â†’ Phase 1 â†’ Phase 2 â†’ Phase 3 â†’ Phase 4 â†’ Phase 5
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
OpenSearch hoáº·c Elasticsearch: BM25 / exact phrase search
Qdrant: dense vector search
Neo4j: graph expansion tá»« Phase 8
```

### 2.3. Models

```text
Embedding:
- darklethelong/vnlegal-lal

Generator:
- Qwen3-8B qua vLLM hoáº·c Ollama
- Qwen2.5-7B-Instruct fallback

Reranker:
- chá»‰ thÃªm tá»« Phase 7
```

---

## 3. CÃ¢y thÆ° má»¥c má»¥c tiÃªu

```text
Legal_Graph_RAG/
â”œâ”€â”€ context.md
â”œâ”€â”€ legal_rag_phase_plan_v3.md
â”œâ”€â”€ codex_task_prompts_vi_v3.md
â”œâ”€â”€ skills/
â”‚
â”œâ”€â”€ backend/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ config/
â”‚   â”œâ”€â”€ infrastructure/
â”‚   â”œâ”€â”€ schema/
â”‚   â”œâ”€â”€ knowledge_processing/
â”‚   â”œâ”€â”€ indexing/
â”‚   â”œâ”€â”€ query_analysis/
â”‚   â”œâ”€â”€ retrieval/
â”‚   â”œâ”€â”€ qa/
â”‚   â”œâ”€â”€ prompts/
â”‚   â”œâ”€â”€ evaluation/
â”‚   â””â”€â”€ submission/
â”‚
â”œâ”€â”€ data/
â”‚   â”œâ”€â”€ raw/
â”‚   â”‚   â””â”€â”€ R2AIStage1DATA.json
â”‚   â”œâ”€â”€ processed/
â”‚   â””â”€â”€ outputs/
â”‚
â”œâ”€â”€ scripts/
â”œâ”€â”€ tests/
â”œâ”€â”€ notebooks/
â”œâ”€â”€ docker-compose.yml
â”œâ”€â”€ requirements.txt
â”œâ”€â”€ .env.example
â”œâ”€â”€ .gitignore
â””â”€â”€ README.md
```

---

# Phase 0 â€” Project Setup

## P0.T1 â€” Táº¡o skeleton project

### Má»¥c tiÃªu

Táº¡o cÃ¢y thÆ° má»¥c vÃ  package structure ban Ä‘áº§u.

### Codex Prompt

DÃ¹ng prompt: `P0.T1` trong `codex_task_prompts_vi_v3.md`.

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
[x] Táº¥t cáº£ folder má»¥c tiÃªu tá»“n táº¡i.
[x] CÃ¡c Python package cÃ³ __init__.py.
[x] KhÃ´ng táº¡o business logic á»Ÿ task nÃ y.
[x] KhÃ´ng xÃ³a file hiá»‡n cÃ³ náº¿u khÃ´ng cáº§n thiáº¿t.
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

## P0.T2 â€” Config vÃ  settings

### Má»¥c tiÃªu

Táº¡o config dÃ¹ng chung cho path, model vÃ  retrieval.

### Codex Prompt

DÃ¹ng prompt: `P0.T2`.

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
[x] Config Ä‘á»c Ä‘Æ°á»£c tá»« YAML.
[x] CÃ³ default path cho raw/processed/output.
[x] CÃ³ default model names.
[x] KhÃ´ng hard-code path trong business logic.
[x] CÃ³ .env.example nhÆ°ng khÃ´ng commit secret.
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
In ra settings object hoáº·c dict config há»£p lá»‡, khÃ´ng lá»—i import.
```

---

## P0.T3 â€” Docker compose baseline

### Má»¥c tiÃªu

Táº¡o Docker services cáº§n cho Phase 2 trá»Ÿ Ä‘i.

### Codex Prompt

DÃ¹ng prompt: `P0.T3`.

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
[ ] docker-compose.yml cÃ³ qdrant.
[ ] docker-compose.yml cÃ³ opensearch.
[ ] docker-compose.yml cÃ³ neo4j nhÆ°ng Phase 1 chÆ°a cáº§n dÃ¹ng.
[ ] CÃ³ volume persistent cho service cáº§n thiáº¿t.
[ ] CÃ³ env sample rÃµ rÃ ng.
```

### User-run commands

```bash
docker compose config
docker compose up -d qdrant opensearch
docker compose ps
```

### Expected result

```text
Docker compose config há»£p lá»‡.
qdrant vÃ  opensearch á»Ÿ tráº¡ng thÃ¡i running/healthy hoáº·c Ã­t nháº¥t started.
```

---

# Phase 1 â€” Data Loading + Canonical Corpus

## Output chung cá»§a Phase 1

```text
data/processed/test_questions.parquet
data/processed/phapdien_articles.parquet
data/processed/anle_units.parquet
data/processed/legal_documents.parquet
data/processed/legal_articles.parquet
data/processed/phapdien_to_vbpl_map.parquet
```

---

## P1.T1 â€” Schema Pydantic

### Má»¥c tiÃªu

Táº¡o schema ná»™i bá»™ cho toÃ n pipeline.

### Codex Prompt

DÃ¹ng prompt: `P1.T1`.

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
[ ] CÃ³ TestQuestion schema.
[ ] CÃ³ LegalDocument schema.
[ ] CÃ³ LegalArticle schema.
[ ] LegalArticle cÃ³ relevant_article_string property.
[ ] LegalArticle cÃ³ relevant_doc_string property.
[ ] CÃ³ schema cho submission item.
[ ] Pydantic validation cháº¡y Ä‘Æ°á»£c.
```

### User-run commands

```bash
python - <<'PY'
from backend.schema.legal_article import LegalArticle

a = LegalArticle(
    article_id="04/2017/QH14|Luáº­t 04/2017/QH14 Luáº­t Há»— trá»£ doanh nghiá»‡p nhá» vÃ  vá»«a|Äiá»u 4",
    law_id="04/2017/QH14",
    law_title="Luáº­t 04/2017/QH14 Luáº­t Há»— trá»£ doanh nghiá»‡p nhá» vÃ  vá»«a",
    article_no="Äiá»u 4",
    article_text="Ná»™i dung Ä‘iá»u luáº­t..."
)
print(a.relevant_article_string)
print(a.relevant_doc_string)
PY
```

### Expected result

```text
04/2017/QH14|Luáº­t 04/2017/QH14 Luáº­t Há»— trá»£ doanh nghiá»‡p nhá» vÃ  vá»«a|Äiá»u 4
04/2017/QH14|Luáº­t 04/2017/QH14 Luáº­t Há»— trá»£ doanh nghiá»‡p nhá» vÃ  vá»«a
```

---

## P1.T2 â€” Text normalization

### Má»¥c tiÃªu

Táº¡o utilities chuáº©n hÃ³a text phÃ¡p luáº­t tiáº¿ng Viá»‡t.

### Codex Prompt

DÃ¹ng prompt: `P1.T2`.

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
[ ] NBSP Ä‘Æ°á»£c thay báº±ng space thÆ°á»ng.
[ ] Gá»™p khoáº£ng tráº¯ng láº·p.
[ ] "Äiá»u 04." -> "Äiá»u 4".
[ ] "Ä‘iá»u 7a" -> "Äiá»u 7a".
[ ] Function xá»­ lÃ½ None an toÃ n.
[ ] CÃ³ pytest cho normalization.
```

### User-run commands

```bash
pytest tests/test_normalize_text.py -q
python - <<'PY'
from backend.knowledge_processing.normalize_text import normalize_article_no
print(normalize_article_no("Äiá»u 04."))
print(normalize_article_no("Ä‘iá»u 7a"))
PY
```

### Expected result

```text
Äiá»u 4
Äiá»u 7a
```

---

## P1.T3 â€” Hugging Face generic loader

### Má»¥c tiÃªu

Táº¡o helper chung Ä‘á»ƒ load HF datasets sang Polars.

### Codex Prompt

DÃ¹ng prompt: `P1.T3`.

### Deliverables

```text
backend/knowledge_processing/hf_loader.py
```

### Acceptance Criteria

```text
[ ] CÃ³ function load_hf_dataset_to_polars().
[ ] Support dataset_name, config_name, split.
[ ] Return Polars DataFrame.
[ ] CÃ³ save_parquet() helper.
[ ] KhÃ´ng gá»i loader trong import-time.
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
In ra shape vÃ  columns cá»§a dataset phapdien.
```

---

## P1.T4 â€” Load testset

### Má»¥c tiÃªu

Load file `R2AIStage1DATA.json` thÃ nh parquet.

### Codex Prompt

DÃ¹ng prompt: `P1.T4`.

### Deliverables

```text
backend/knowledge_processing/load_testset.py
scripts/01_load_testset.py
tests/test_load_testset.py
```

### Acceptance Criteria

```text
[ ] Validate JSON lÃ  list.
[ ] Má»—i item cÃ³ id vÃ  question.
[ ] id convert Ä‘Æ°á»£c sang int.
[ ] question khÃ´ng rá»—ng sau normalize.
[ ] KhÃ´ng cÃ³ duplicate id.
[ ] Output lÃ  data/processed/test_questions.parquet.
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
Sá»‘ dÃ²ng = 2000.
id unique = 2000.
```

---

## P1.T5 â€” Load phapdien

### Má»¥c tiÃªu

Load `tmquan/phapdien-moj-gov-vn` config `articles`.

### Codex Prompt

DÃ¹ng prompt: `P1.T5`.

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
[ ] Load Ä‘Æ°á»£c dataset phapdien.
[ ] content_text khÃ´ng rá»—ng vá»›i pháº§n lá»›n rows.
[ ] source_note_text Ä‘Æ°á»£c giá»¯ láº¡i.
[ ] source_links Ä‘Æ°á»£c serialize thÃ nh JSON string.
[ ] KhÃ´ng dÃ¹ng article_title lÃ m citation chÃ­nh thá»©c.
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
Táº¡o Ä‘Æ°á»£c phapdien_articles.parquet vÃ  in sample rows.
```

---

## P1.T6 â€” Load anle

### Má»¥c tiÃªu

Load `tmquan/anle-toaan-gov-vn` config `sentences`.

### Codex Prompt

DÃ¹ng prompt: `P1.T6`.

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
[ ] CÃ³ unit_id unique.
[ ] CÃ³ text khÃ´ng rá»—ng.
[ ] KhÃ´ng dÃ¹ng embedding cÃ³ sáºµn tá»« dataset.
[ ] anle chá»‰ lÃ  auxiliary source.
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
Táº¡o Ä‘Æ°á»£c anle_units.parquet vÃ  in sample rows.
```

---

## P1.T7 â€” Load VBPL documents

### Má»¥c tiÃªu

Load `tmquan/vbpl-vn` thÃ nh document-level parquet.

### Codex Prompt

DÃ¹ng prompt: `P1.T7`.

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
[ ] Load Ä‘Æ°á»£c VBPL dataset.
[ ] CÃ³ markdown/body text.
[ ] normalized_title Ä‘Æ°á»£c táº¡o á»•n Ä‘á»‹nh.
[ ] CÃ³ log cho rows thiáº¿u law_id hoáº·c markdown.
[ ] KhÃ´ng extract article trong task nÃ y.
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
Táº¡o Ä‘Æ°á»£c legal_documents.parquet.
```

---

## P1.T8 â€” Extract legal articles

### Má»¥c tiÃªu

TÃ¡ch Äiá»u luáº­t tá»« `legal_documents.parquet`.

### Codex Prompt

DÃ¹ng prompt: `P1.T8`.

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
[ ] Extract Ä‘Æ°á»£c article-level rows.
[ ] article_id format: law_id|law_title|Äiá»u X.
[ ] article_id unique.
[ ] KhÃ´ng cÃ³ article thiáº¿u law_id/law_title/article_no/article_text.
[ ] CÃ³ log vÄƒn báº£n khÃ´ng extract Ä‘Æ°á»£c Äiá»u.
[ ] CÃ³ test cho regex article extraction á»Ÿ má»©c cÆ¡ báº£n.
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
Táº¡o Ä‘Æ°á»£c legal_articles.parquet.
unique article_id báº±ng sá»‘ dÃ²ng.
```

---

## P1.T9 â€” Map phapdien to VBPL

### Má»¥c tiÃªu

Map phapdien hits sang canonical legal articles.

### Codex Prompt

DÃ¹ng prompt: `P1.T9`.

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
[ ] CÃ³ phapdien_id.
[ ] CÃ³ legal_article_id.
[ ] CÃ³ law_id, law_title, article_no.
[ ] CÃ³ mapping_score.
[ ] CÃ³ mapping_method.
[ ] Mapping dÆ°á»›i threshold Ä‘Æ°á»£c log ra file/debug.
[ ] KhÃ´ng dÃ¹ng phapdien article_title lÃ m official citation.
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
Táº¡o Ä‘Æ°á»£c phapdien_to_vbpl_map.parquet vá»›i mapping_score.
```

---

## P1.T10 â€” Build corpus orchestration

### Má»¥c tiÃªu

Gá»™p toÃ n bá»™ Phase 1 thÃ nh má»™t script.

### Codex Prompt

DÃ¹ng prompt: `P1.T10`.

### Deliverables

```text
backend/knowledge_processing/build_corpus.py
scripts/01_build_corpus.py
```

### Acceptance Criteria

```text
[ ] scripts/01_build_corpus.py gá»i cÃ¡c module Phase 1 theo thá»© tá»±.
[ ] Script khÃ´ng chá»©a business logic lá»›n.
[ ] CÃ³ logging tá»«ng step.
[ ] CÃ³ option skip_existing náº¿u phÃ¹ há»£p.
[ ] NgÆ°á»i dÃ¹ng tá»± cháº¡y script.
```

### User-run commands

```bash
python scripts/01_build_corpus.py
ls -lh data/processed
```

### Expected result

```text
Táº¡o Ä‘á»§ 6 parquet files cá»§a Phase 1.
```

## P1.T11 â€” Prepare Indexable Corpus

### Má»¥c tiÃªu

Táº¡o lá»›p dá»¯ liá»‡u trung gian phá»¥c vá»¥ indexing cho Phase 2, nháº±m trÃ¡nh Ä‘Æ°a trá»±c tiáº¿p `legal_articles.parquet` vÃ  `phapdien_articles.parquet` vÃ o OpenSearch/Qdrant khi dá»¯ liá»‡u cÃ²n cÃ³ outlier quÃ¡ dÃ i hoáº·c row rá»—ng.

Task nÃ y **khÃ´ng thay Ä‘á»•i canonical corpus**. CÃ¡c file canonical sau váº«n lÃ  source of truth:

```text
data/processed/legal_articles.parquet
data/processed/phapdien_articles.parquet
```

Thay vÃ o Ä‘Ã³, task nÃ y táº¡o cÃ¡c file derived/indexable:

```text
data/processed/legal_article_chunks.parquet
data/processed/phapdien_articles_index.parquet
```

Phase 2 sáº½ index tá»« cÃ¡c file derived nÃ y.

---

### Bá»‘i cáº£nh sau Phase 1

Phase 1 Ä‘Ã£ build xong vá»›i káº¿t quáº£:

```text
test_questions: 2.000 rows, unique id 2.000
phapdien_articles: 64.464 rows, cÃ³ 406 rows empty content_text
anle_units: 273.379 rows, unit_id unique, khÃ´ng empty text
legal_documents: 146.555 rows, khÃ´ng thiáº¿u law_id/markdown
legal_articles: 1.015.680 rows, article_id unique báº±ng sá»‘ dÃ²ng, khÃ´ng thiáº¿u required fields
phapdien_to_vbpl_map: 60.053 rows, khÃ´ng thiáº¿u legal_article_id
mapping coverage phapdien: 93.16%
low-confidence/unmapped phapdien: 4.411 rows, Ä‘Ã£ cÃ³ debug parquet
```

Risk cáº§n xá»­ lÃ½ trÆ°á»›c Phase 2:

```text
1. legal_articles.article_text cÃ³ outlier ráº¥t lá»›n, max khoáº£ng 2.31M kÃ½ tá»±.
2. phapdien cÃ³ 406 rows rá»—ng content_text.
3. 4.411 phapdien rows chÆ°a map Ä‘Æ°á»£c, nhÆ°ng táº¡m thá»i defer vÃ¬ khÃ´ng áº£nh hÆ°á»Ÿng nguyÃªn táº¯c citation.
```

---

### NguyÃªn táº¯c báº¯t buá»™c

```text
[ ] KhÃ´ng sá»­a trá»±c tiáº¿p legal_articles.parquet.
[ ] KhÃ´ng sá»­a trá»±c tiáº¿p phapdien_articles.parquet.
[ ] legal_articles.parquet váº«n lÃ  source of truth cho relevant_docs/relevant_articles.
[ ] Index corpus chá»‰ phá»¥c vá»¥ retrieval.
[ ] Khi retrieval hit vÃ o chunk, output cuá»‘i cÃ¹ng váº«n pháº£i group vá» parent article_id.
[ ] KhÃ´ng dÃ¹ng chunk_id lÃ m citation.
[ ] KhÃ´ng xá»­ lÃ½ 4.411 unmapped phapdien trong task nÃ y.
```

---

### Deliverables

Táº¡o module:

```text
backend/knowledge_processing/prepare_index_corpus.py
```

Táº¡o script:

```text
scripts/01_prepare_index_corpus.py
```

Táº¡o output files:

```text
data/processed/legal_article_chunks.parquet
data/processed/phapdien_articles_index.parquet
data/processed/debug/legal_article_text_length_report.csv
data/processed/debug/legal_article_chunk_report.csv
data/processed/debug/phapdien_empty_content_report.csv
```

Táº¡o test náº¿u phÃ¹ há»£p:

```text
tests/test_prepare_index_corpus.py
```

---

### Output 1 â€” legal_article_chunks.parquet

Input:

```text
data/processed/legal_articles.parquet
```

Output:

```text
data/processed/legal_article_chunks.parquet
```

Schema Ä‘á» xuáº¥t:

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
[ ] Náº¿u article_text ngáº¯n, táº¡o 1 chunk.
[ ] Náº¿u article_text quÃ¡ dÃ i, split thÃ nh nhiá»u chunks.
[ ] KhÃ´ng táº¡o chunk_text rá»—ng.
[ ] KhÃ´ng lÃ m máº¥t parent article_id.
[ ] chunk_text dÃ¹ng cho BM25/vector index.
[ ] article_id dÃ¹ng Ä‘á»ƒ group retrieval result vá» Äiá»u luáº­t canonical.
```

Config máº·c Ä‘á»‹nh:

```yaml
max_chunk_chars: 3000
chunk_overlap_chars: 300
max_article_chars_for_single_doc: 12000
min_text_chars: 20
```

Gá»£i Ã½ xá»­ lÃ½:

```text
- Æ¯u tiÃªn split theo ranh giá»›i Ä‘oáº¡n/khoáº£n/dÃ²ng náº¿u lÃ m Ä‘Æ°á»£c.
- Náº¿u khÃ´ng tÃ¬m Ä‘Æ°á»£c ranh giá»›i phÃ¹ há»£p, fallback split theo character window.
- Overlap khÃ´ng Ä‘Æ°á»£c táº¡o infinite loop.
- Article quÃ¡ ngáº¯n hoáº·c text lá»—i cáº§n Ä‘Æ°á»£c log, khÃ´ng lÃ m crash pipeline.
```

---

### Output 2 â€” phapdien_articles_index.parquet

Input:

```text
data/processed/phapdien_articles.parquet
```

Output:

```text
data/processed/phapdien_articles_index.parquet
```

YÃªu cáº§u:

```text
[ ] Loáº¡i khá»i index input cÃ¡c row cÃ³ content_text null hoáº·c rá»—ng sau strip.
[ ] KhÃ´ng xÃ³a row khá»i phapdien_articles.parquet gá»‘c.
[ ] Giá»¯ cÃ¡c field cáº§n cho retrieval.
```

Fields cáº§n giá»¯:

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

CÃ¡c row rá»—ng Ä‘Æ°á»£c ghi vÃ o:

```text
data/processed/debug/phapdien_empty_content_report.csv
```

---

### Output 3 â€” legal_article_text_length_report.csv

Táº¡o report:

```text
data/processed/debug/legal_article_text_length_report.csv
```

Fields tá»‘i thiá»ƒu:

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

YÃªu cáº§u:

```text
[ ] Sort giáº£m dáº§n theo article_text_char_len.
[ ] DÃ¹ng Ä‘á»ƒ audit cÃ¡c Äiá»u luáº­t outlier quÃ¡ dÃ i.
```

---

### Output 4 â€” legal_article_chunk_report.csv

Táº¡o report:

```text
data/processed/debug/legal_article_chunk_report.csv
```

Report cáº§n cÃ³:

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

CÃ³ thá»ƒ lÆ°u dáº¡ng CSV má»™t dÃ²ng Ä‘á»ƒ dá»… Ä‘á»c báº±ng Polars/Pandas.

---

### Required function

Trong `prepare_index_corpus.py`, táº¡o function chÃ­nh:

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

Return summary dict gá»“m:

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

Táº¡o:

```text
scripts/01_prepare_index_corpus.py
```

Script cáº§n há»— trá»£ argparse:

```text
--max-chunk-chars
--chunk-overlap-chars
--min-text-chars
--max-article-chars-for-single-doc
```

YÃªu cáº§u:

```text
[ ] Script chá»‰ gá»i backend function.
[ ] KhÃ´ng chá»©a business logic lá»›n.
[ ] CÃ³ logging rÃµ tá»«ng bÆ°á»›c.
[ ] In summary cuá»‘i cÃ¹ng.
```

---

### Tests

Táº¡o:

```text
tests/test_prepare_index_corpus.py
```

Test tá»‘i thiá»ƒu:

```text
[ ] Short article táº¡o 1 chunk.
[ ] Long article táº¡o nhiá»u chunks.
[ ] chunk_id giá»¯ parent article_id.
[ ] Overlap khÃ´ng táº¡o infinite loop.
[ ] KhÃ´ng cÃ³ chunk_text rá»—ng.
[ ] phapdien empty content bá»‹ filter khá»i index output.
[ ] legal_articles canonical khÃ´ng bá»‹ modify.
```

---

### Acceptance Criteria

```text
[ ] legal_articles.parquet khÃ´ng bá»‹ sá»­a.
[ ] phapdien_articles.parquet khÃ´ng bá»‹ sá»­a.
[ ] Táº¡o Ä‘Æ°á»£c legal_article_chunks.parquet.
[ ] Táº¡o Ä‘Æ°á»£c phapdien_articles_index.parquet.
[ ] Táº¡o Ä‘Æ°á»£c legal_article_text_length_report.csv.
[ ] Táº¡o Ä‘Æ°á»£c legal_article_chunk_report.csv.
[ ] Táº¡o Ä‘Æ°á»£c phapdien_empty_content_report.csv.
[ ] legal_article_chunks.parquet cÃ³ chunk_id unique.
[ ] Má»—i chunk cÃ³ parent article_id.
[ ] KhÃ´ng cÃ³ chunk_text rá»—ng.
[ ] phapdien_articles_index.parquet khÃ´ng cÃ³ content_text rá»—ng.
[ ] Code cÃ³ type hints.
[ ] Logic chunking cÃ³ comment tiáº¿ng Viá»‡t.
[ ] KhÃ´ng xá»­ lÃ½ 4.411 unmapped phapdien trong task nÃ y.
```

---

### User-run commands

Cháº¡y test:

```bash
pytest tests/test_prepare_index_corpus.py -q
```

Cháº¡y prepare index corpus:

```bash
python scripts/01_prepare_index_corpus.py
```

Kiá»ƒm tra output:

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
legal_article_chunks.parquet tá»“n táº¡i
phapdien_articles_index.parquet tá»“n táº¡i
debug reports tá»“n táº¡i
chunk_id unique = sá»‘ dÃ²ng chunks
empty chunk_text = 0
empty phapdien content_text = 0
```

---

### Phase 2 dependency update

Sau task nÃ y, Phase 2 khÃ´ng index trá»±c tiáº¿p full text tá»«:

```text
data/processed/legal_articles.parquet
data/processed/phapdien_articles.parquet
```

Thay vÃ o Ä‘Ã³, Phase 2 index tá»«:

```text
data/processed/legal_article_chunks.parquet
data/processed/phapdien_articles_index.parquet
data/processed/anle_units.parquet
```

Khi retrieval hit vÃ o `legal_article_chunks`, há»‡ thá»‘ng pháº£i group káº¿t quáº£ vá» parent `article_id` trÆ°á»›c khi article selection vÃ  submission builder xá»­ lÃ½.

---

# Phase 2 â€” Indexing

## NguyÃªn táº¯c chung cá»§a Phase 2

Phase 2 xÃ¢y dá»±ng cÃ¡c index phá»¥c vá»¥ retrieval. Phase 2 **khÃ´ng sinh citation** vÃ  **khÃ´ng thay Ä‘á»•i canonical corpus**.

Nguá»“n dá»¯ liá»‡u báº¯t buá»™c:

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

Quy táº¯c báº¯t buá»™c:

```text
[ ] KhÃ´ng index trá»±c tiáº¿p full article_text tá»« legal_articles.parquet vÃ o BM25/vector legal retrieval.
[ ] BM25/vector legal retrieval pháº£i dÃ¹ng legal_article_chunks.parquet.
[ ] legal_articles.parquet chá»‰ dÃ¹ng cho exact lookup, canonical registry, citation vÃ  submission.
[ ] chunk_id khÃ´ng Ä‘Æ°á»£c dÃ¹ng lÃ m citation.
[ ] Retrieval hits tá»« legal chunks pháº£i giá»¯ parent article_id.
[ ] Retrieval layer pháº£i dedup/group chunk hits vá» article_id trÆ°á»›c article selection.
[ ] Phapdien index pháº£i dÃ¹ng phapdien_articles_index.parquet, khÃ´ng dÃ¹ng phapdien_articles.parquet gá»‘c.
[ ] Neo4j khÃ´ng thuá»™c Phase 2; Neo4j chá»‰ triá»ƒn khai á»Ÿ Phase 8.
```

---

## P2.T1 â€” Infrastructure clients

### Codex Prompt

DÃ¹ng prompt: `P2.T1`.

### Deliverables

```text
backend/infrastructure/search_engine/opensearch_client.py
backend/infrastructure/vector_store/qdrant_client.py
backend/infrastructure/database/duckdb_client.py
```

### Acceptance Criteria

```text
[ ] OpenSearch client cÃ³ health_check().
[ ] Qdrant client cÃ³ health_check().
[ ] DuckDB helper Ä‘á»c parquet Ä‘Æ°á»£c.
[ ] KhÃ´ng táº¡o index á»Ÿ import-time.
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

## P2.T2 â€” vnlegal-lal embedding wrapper

### Codex Prompt

DÃ¹ng prompt: `P2.T2`.

### Deliverables

```text
backend/infrastructure/embedding_models/vnlegal_lal.py
```

### Acceptance Criteria

```text
[ ] CÃ³ encode_query().
[ ] CÃ³ encode_documents().
[ ] Query cÃ³ instruction prefix.
[ ] Document khÃ´ng cÃ³ instruction prefix.
[ ] Output vector dimension = 1024 náº¿u model load Ä‘Ãºng.
[ ] CÃ³ batching.
[ ] CÃ³ normalize vector.
[ ] Vá»›i vnlegal-lal, Æ°u tiÃªn AutoModel + last-token pooling theo model card; khÃ´ng rely vÃ o SentenceTransformer fallback mean pooling náº¿u Ä‘Ã£ cÃ³ wrapper chuáº©n.
```

### User-run commands

```bash
python - <<'PY'
from backend.infrastructure.embedding_models.vnlegal_lal import VNLegalLALEmbedder
m = VNLegalLALEmbedder(device="cuda", batch_size=2, max_length=512)
v = m.encode_query("Doanh nghiá»‡p nhá» vÃ  vá»«a lÃ  gÃ¬?")
print(len(v), v[:5])
PY
```

---

## P2.T3 â€” Build BM25 indexes

### Codex Prompt

DÃ¹ng prompt: `P2.T3`.

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
[ ] Build Ä‘Æ°á»£c legal_article_chunks_bm25.
[ ] Build Ä‘Æ°á»£c phapdien_articles_bm25.
[ ] Build Ä‘Æ°á»£c anle_units_bm25.
[ ] Legal BM25 Ä‘á»c legal_article_chunks.parquet, khÃ´ng Ä‘á»c legal_articles.parquet.
[ ] Legal BM25 index dÃ¹ng chunk_text lÃ m text chÃ­nh.
[ ] Payload legal BM25 giá»¯ cáº£ chunk_id vÃ  parent article_id.
[ ] Phapdien BM25 Ä‘á»c phapdien_articles_index.parquet.
[ ] CÃ³ recreate flag.
[ ] CÃ³ max_rows/sample option náº¿u phÃ¹ há»£p.
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

## P2.T4 â€” Build vector indexes

### Codex Prompt

DÃ¹ng prompt: `P2.T4`.

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

### Legal chunk text format Ä‘á»ƒ embed

```text
TÃªn vÄƒn báº£n: {law_title}
Äiá»u: {article_no}
TiÃªu Ä‘á» Ä‘iá»u: {article_title}
Ná»™i dung chunk:
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
[ ] Build Ä‘Æ°á»£c legal_article_chunks_dense.
[ ] Build Ä‘Æ°á»£c phapdien_articles_dense.
[ ] Build Ä‘Æ°á»£c anle_units_dense.
[ ] Legal vector index Ä‘á»c legal_article_chunks.parquet, khÃ´ng Ä‘á»c legal_articles.parquet.
[ ] Legal vector index embed chunk_text kÃ¨m legal context.
[ ] Payload giá»¯ chunk_id vÃ  parent article_id.
[ ] KhÃ´ng dÃ¹ng chunk_id lÃ m canonical citation id.
[ ] Phapdien vector Ä‘á»c phapdien_articles_index.parquet.
[ ] CÃ³ batching.
[ ] CÃ³ recreate flag.
[ ] CÃ³ resume/skip option náº¿u phÃ¹ há»£p.
[ ] Náº¿u Ä‘á»•i tá»« article-level sang chunk-level thÃ¬ pháº£i rebuild vá»›i recreate=True, resume=False.
[ ] KhÃ´ng trá»™n embedding tá»« mean pooling vÃ  last-token pooling trong cÃ¹ng collection.
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

## P2.T5 â€” Build exact index

### Codex Prompt

DÃ¹ng prompt: `P2.T5`.

### Deliverables

```text
backend/indexing/build_exact_index.py
data/processed/exact_index.json hoáº·c parquet
```

### Input

```text
data/processed/legal_articles.parquet
```

### Acceptance Criteria

```text
[ ] Exact index váº«n Ä‘á»c legal_articles.parquet.
[ ] Exact lookup theo law_id.
[ ] Exact lookup theo article_no.
[ ] Exact lookup theo law_id + article_no.
[ ] Extract Ä‘Æ°á»£c tÃ i khoáº£n káº¿ toÃ¡n náº¿u phÃ¹ há»£p.
[ ] Extract Ä‘Æ°á»£c deadline number náº¿u phÃ¹ há»£p.
[ ] Exact index load nhanh.
[ ] KhÃ´ng dÃ¹ng legal_article_chunks.parquet cho exact citation registry.
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

Báº¡n Ä‘ang code trong repository `Legal_Graph_RAG`.

TrÆ°á»›c khi code, hÃ£y Ä‘á»c:

* `context.md`
* `legal_rag_phase_plan_v3.md`
* `codex_task_prompts_vi_v3.md`
* `backend/indexing/build_exact_index.py` náº¿u Ä‘Ã£ tá»“n táº¡i
* `tests/test_build_exact_index.py` náº¿u Ä‘Ã£ tá»“n táº¡i
* `skills/11_code_quality_testing.md`

### Bá»‘i cáº£nh hiá»‡n táº¡i

P2.T5 Ä‘Ã£ build Ä‘Æ°á»£c file:

```text
data/processed/exact_index.json
```

Káº¿t quáº£ kiá»ƒm tra:

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

`exact_index.json` Ä‘á»c Ä‘Æ°á»£c vÃ  khÃ´ng lá»—i JSON. `articles` khÃ´ng chá»©a `article_text`, chá»‰ chá»©a metadata ngáº¯n:

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

Váº¥n Ä‘á» chÃ­nh: `exact_index.json` quÃ¡ lá»›n vÃ¬ cÃ¡c inverted indexes lÆ°u láº·p láº¡i `article_id` dÃ i nhiá»u láº§n. Náº¿u Phase 4 runtime dÃ¹ng `json.load()` file 1.9GB thÃ¬ tá»‘n RAM, startup cháº­m vÃ  khÃ´ng phÃ¹ há»£p Ä‘á»ƒ cháº¡y retrieval nhiá»u láº§n.

- Náº¿u project Ä‘Ã£ chá»n DuckDB lÃ m runtime exact index, cáº­p nháº­t deliverable thÃ nh data/processed/exact_index.duckdb.
- KhÃ´ng giá»¯ mÃ´ táº£ báº¯t buá»™c exact_index/ folder Parquet náº¿u khÃ´ng cÃ²n triá»ƒn khai hÆ°á»›ng Ä‘Ã³.

### Má»¥c tiÃªu task

Tá»‘i Æ°u P2.T5 Ä‘á»ƒ táº¡o thÃªm exact index runtime-friendly dáº¡ng thÆ° má»¥c nhiá»u file Parquet/JSON metadata, thay vÃ¬ phá»¥ thuá»™c vÃ o má»™t file JSON lá»›n.

Má»¥c tiÃªu má»›i:

```text
data/processed/exact_index/
â”œâ”€â”€ articles.parquet
â”œâ”€â”€ by_law_id.parquet
â”œâ”€â”€ by_article_no.parquet
â”œâ”€â”€ by_law_article.parquet
â”œâ”€â”€ accounting_accounts.parquet
â”œâ”€â”€ deadline_numbers.parquet
â”œâ”€â”€ sanction_terms.parquet
â””â”€â”€ metadata.json
```

CÃ³ thá»ƒ giá»¯ `data/processed/exact_index.json` nhÆ° artifact debug/backward-compatible náº¿u code hiá»‡n táº¡i cáº§n, nhÆ°ng runtime Phase 4 nÃªn Æ°u tiÃªn Ä‘á»c thÆ° má»¥c `data/processed/exact_index/`.

### YÃªu cáº§u thiáº¿t káº¿ báº¯t buá»™c

1. Exact index váº«n chá»‰ Ä‘á»c:

```text
data/processed/legal_articles.parquet
```

2. KhÃ´ng Ä‘á»c:

```text
data/processed/legal_article_chunks.parquet
```

3. KhÃ´ng dÃ¹ng OpenSearch/Qdrant.

4. KhÃ´ng gá»i LLM.

5. KhÃ´ng sinh `results.json`.

6. KhÃ´ng chá»n final `relevant_articles`.

7. KhÃ´ng sá»­a BM25/vector index logic.

8. KhÃ´ng thay Ä‘á»•i canonical `legal_articles.parquet`.

9. KhÃ´ng dÃ¹ng `chunk_id` trong exact index.

10. Exact index runtime artifact pháº£i trÃ¡nh láº·p chuá»—i `article_id` dÃ i quÃ¡ nhiá»u láº§n báº±ng cÃ¡ch dÃ¹ng `article_idx` integer.

### Schema Ä‘á» xuáº¥t

#### 1. `articles.parquet`

Má»—i dÃ²ng lÃ  má»™t canonical article.

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

YÃªu cáº§u:

```text
article_idx lÃ  int liÃªn tá»¥c tá»« 0 Ä‘áº¿n n-1.
article_id unique.
KhÃ´ng cÃ³ duplicate article_idx.
KhÃ´ng chá»©a article_text Ä‘á»ƒ trÃ¡nh file quÃ¡ lá»›n.
relevant_doc_string = law_id|law_title
relevant_article_string = law_id|law_title|article_no
```

#### 2. `by_law_id.parquet`

Long-table lookup:

```text
key
article_idx
```

Trong Ä‘Ã³ `key` lÃ  `normalized_law_id`.

#### 3. `by_article_no.parquet`

Long-table lookup:

```text
key
article_idx
```

Trong Ä‘Ã³ `key` lÃ  `normalized_article_no`.

LÆ°u Ã½: má»™t `article_no` nhÆ° â€œÄiá»u 4â€ cÃ³ thá»ƒ map tá»›i ráº¥t nhiá»u `article_idx`, khÃ´ng Ä‘Æ°á»£c assume unique.

#### 4. `by_law_article.parquet`

Long-table lookup cho law + article.

Required columns:

```text
key
article_idx
key_type
```

Trong Ä‘Ã³ `key_type` cÃ³ thá»ƒ lÃ :

```text
law_id_article_no
law_title_article_no
```

Key nÃªn Ä‘Æ°á»£c normalize á»•n Ä‘á»‹nh, vÃ­ dá»¥:

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

Trong Ä‘Ã³ `key` lÃ  mÃ£ tÃ i khoáº£n káº¿ toÃ¡n hoáº·c account pattern Ä‘Ã£ extract.

#### 6. `deadline_numbers.parquet`

Long-table lookup:

```text
key
article_idx
```

Trong Ä‘Ã³ `key` lÃ  cÃ¡c biá»ƒu thá»©c thá»i háº¡n/sá»‘ ngÃ y/sá»‘ thÃ¡ng/nÄƒm Ä‘Ã£ extract náº¿u logic hiá»‡n táº¡i Ä‘Ã£ cÃ³.

#### 7. `sanction_terms.parquet`

Long-table lookup:

```text
key
article_idx
```

Trong Ä‘Ã³ `key` lÃ  term/amount/pattern liÃªn quan xá»­ pháº¡t náº¿u logic hiá»‡n táº¡i Ä‘Ã£ cÃ³.

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

Sá»‘ rows pháº£i ghi Ä‘Ãºng theo artifact thá»±c táº¿.

### Function/API cáº§n cÃ³

Trong `backend/indexing/build_exact_index.py`, táº¡o hoáº·c sá»­a function:

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

YÃªu cáº§u:

```text
input_path default = data/processed/legal_articles.parquet tá»« settings/path config náº¿u cÃ³.
output_dir default = data/processed/exact_index.
Náº¿u recreate=True thÃ¬ xÃ³a hoáº·c overwrite output_dir an toÃ n.
write_legacy_json=False máº·c Ä‘á»‹nh Ä‘á»ƒ trÃ¡nh táº¡o láº¡i file JSON 1.9GB náº¿u khÃ´ng cáº§n.
Náº¿u write_legacy_json=True thÃ¬ cÃ³ thá»ƒ táº¡o exact_index.json backward-compatible.
```

Náº¿u hiá»‡n táº¡i code Ä‘Ã£ cÃ³ `build_exact_index()` signature khÃ¡c, hÃ£y giá»¯ backward compatibility náº¿u há»£p lÃ½, nhÆ°ng Æ°u tiÃªn runtime artifact má»›i.

### Runtime helper optional nhÆ°ng khuyáº¿n nghá»‹

Náº¿u phÃ¹ há»£p, táº¡o helper class nháº¹:

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

KhÃ´ng báº¯t buá»™c pháº£i tá»‘i Æ°u báº±ng DuckDB ngay, nhÆ°ng náº¿u dÃ¹ng DuckDB Ä‘á»ƒ query Parquet lazy Ä‘Æ°á»£c thÃ¬ cÃ ng tá»‘t. KhÃ´ng Ä‘Æ°á»£c load toÃ n bá»™ `exact_index.json` trong runtime helper.

### Files dá»± kiáº¿n sá»­a/táº¡o

CÃ³ thá»ƒ sá»­a/táº¡o:

```text
backend/indexing/build_exact_index.py
tests/test_build_exact_index.py
scripts/02_build_exact_index.py
```

Náº¿u Ä‘Ã£ cÃ³ file tÆ°Æ¡ng á»©ng, cáº­p nháº­t thay vÃ¬ táº¡o duplicate.

KhÃ´ng sá»­a:

```text
backend/indexing/build_bm25_index.py
backend/indexing/build_vector_index.py
backend/retrieval/*
```

trá»« khi tháº­t sá»± cáº§n cáº­p nháº­t import nhá» vÃ  pháº£i bÃ¡o rÃµ trÆ°á»›c.

### Acceptance Criteria

* [ ] `build_exact_index(recreate=True)` táº¡o Ä‘Æ°á»£c thÆ° má»¥c `data/processed/exact_index/`.
* [ ] Táº¡o Ä‘á»§ cÃ¡c files:

  * `articles.parquet`
  * `by_law_id.parquet`
  * `by_article_no.parquet`
  * `by_law_article.parquet`
  * `accounting_accounts.parquet`
  * `deadline_numbers.parquet`
  * `sanction_terms.parquet`
  * `metadata.json`
* [ ] `articles.parquet` cÃ³ `article_idx` integer unique.
* [ ] `articles.parquet` cÃ³ `article_id` unique.
* [ ] `articles.parquet` khÃ´ng chá»©a `article_text`.
* [ ] Inverted indexes dÃ¹ng `article_idx`, khÃ´ng dÃ¹ng láº·p `article_id`.
* [ ] `relevant_doc_string` Ä‘Ãºng format `law_id|law_title`.
* [ ] `relevant_article_string` Ä‘Ãºng format `law_id|law_title|article_no`.
* [ ] `by_article_no.parquet` cho phÃ©p má»™t key map nhiá»u `article_idx`.
* [ ] `by_law_article.parquet` há»— trá»£ cáº£ key theo law_id + article_no vÃ  law_title + article_no.
* [ ] `metadata.json` ghi Ä‘Ãºng row counts.
* [ ] KhÃ´ng gá»i OpenSearch/Qdrant/LLM.
* [ ] KhÃ´ng cháº¡y lá»‡nh thay tÃ´i.

### Test cáº§n thÃªm/cáº­p nháº­t

Táº¡o/cáº­p nháº­t `tests/test_build_exact_index.py`.

Test tá»‘i thiá»ƒu dÃ¹ng fixture nhá», khÃ´ng dÃ¹ng full corpus:

1. Build exact index tá»« fixture `legal_articles.parquet` nhá».
2. Output Ä‘á»§ files.
3. `articles.parquet` khÃ´ng cÃ³ `article_text`.
4. `article_idx` unique.
5. `article_id` unique.
6. `relevant_doc_string` Ä‘Ãºng.
7. `relevant_article_string` Ä‘Ãºng.
8. `by_law_article` lookup Ä‘Æ°á»£c Ä‘Ãºng article theo law_id + article_no.
9. `by_law_article` lookup Ä‘Æ°á»£c Ä‘Ãºng article theo law_title + article_no.
10. `by_article_no` cÃ³ thá»ƒ tráº£ nhiá»u article cho cÃ¹ng â€œÄiá»u 1â€.
11. `metadata.json` cÃ³ `format_version = exact_index_parquet_v1`.

### Lá»‡nh tÃ´i sáº½ tá»± cháº¡y

Sau khi báº¡n code xong, tÃ´i sáº½ cháº¡y:

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

* `articles` khoáº£ng 1,015,680 rows.
* `article_id unique` = sá»‘ rows.
* `article_idx unique` = sá»‘ rows.
* `has article_text: False`.
* CÃ¡c inverted index cÃ³ columns gá»“m `key`, `article_idx`, vÃ  thÃªm `key_type` náº¿u cáº§n.
* Tá»•ng size thÆ° má»¥c `exact_index/` pháº£i nhá» hÆ¡n Ä‘Ã¡ng ká»ƒ so vá»›i `exact_index.json` 1.9GB.

### Quy trÃ¬nh lÃ m viá»‡c báº¯t buá»™c

TrÆ°á»›c khi sá»­a code, hÃ£y bÃ¡o cÃ¡o:

```text
Scope báº¡n hiá»ƒu:
- ...

Files dá»± kiáº¿n sá»­a:
- ...

Test command tÃ´i cáº§n cháº¡y:
- ...
```

Sau Ä‘Ã³ dá»«ng vÃ  chá» tÃ´i xÃ¡c nháº­n, trá»« khi tÃ´i ghi rÃµ â€œtriá»ƒn khai luÃ´nâ€.

Sau khi hoÃ n thÃ nh, bÃ¡o cÃ¡o:

```text
Files changed:
- ...

Logic thay Ä‘á»•i:
- ...

Acceptance Criteria:
- [x] ...
- [ ] ...

Test result:
- ChÆ°a cháº¡y â€” ngÆ°á»i dÃ¹ng cáº§n cháº¡y lá»‡nh bÃªn dÆ°á»›i.

Risk cÃ²n láº¡i:
- ...

Lá»‡nh tÃ´i cáº§n cháº¡y:
- ...
```

## P2.T6 â€” Build indexes orchestration

### Codex Prompt

DÃ¹ng prompt: `P2.T6`.

### Deliverables

```text
scripts/02_build_indexes.py
```

### Acceptance Criteria

```text
[ ] Script gá»i BM25, vector, exact builders.
[ ] CÃ³ logging tá»«ng step.
[ ] KhÃ´ng chá»©a business logic lá»›n.
[ ] CÃ³ option --only bm25|dense|exact náº¿u phÃ¹ há»£p.
[ ] CÃ³ option --max-rows/sample-size náº¿u phÃ¹ há»£p.
[ ] Legal BM25/dense orchestration dÃ¹ng legal_article_chunks.parquet.
[ ] Exact orchestration dÃ¹ng legal_articles.parquet.
[ ] NgÆ°á»i dÃ¹ng tá»± cháº¡y script.
```

### User-run commands

```bash
python scripts/02_build_indexes.py --only bm25 --max-rows 1000
python scripts/02_build_indexes.py --only dense --max-rows 20
python scripts/02_build_indexes.py --only exact
```


# Phase 3 â€” Query Analysis

## P3.T1 â€” Domain router

### Codex Prompt

DÃ¹ng prompt: `P3.T1`.

### Deliverables

```text
backend/query_analysis/domain_router.py
tests/test_domain_router.py
```

### Acceptance Criteria

```text
[ ] classify_domain(question) cháº¡y Ä‘Æ°á»£c.
[ ] CÃ³ domain confidence.
[ ] CÃ³ domain other fallback.
[ ] KhÃ´ng hard-filter retrieval.
```

### User-run commands

```bash
pytest tests/test_domain_router.py -q
```

---

## P3.T2 â€” Answer type classifier

### Codex Prompt

DÃ¹ng prompt: `P3.T2`.

### Deliverables

```text
backend/query_analysis/answer_type_classifier.py
tests/test_answer_type_classifier.py
```

### Acceptance Criteria

```text
[ ] classify_answer_type(question) cháº¡y Ä‘Æ°á»£c.
[ ] Nháº­n diá»‡n deadline/amount/sanction/procedure/dossier/conditions/yes_no/accounting_account.
[ ] CÃ³ fallback general/definition/multi_part.
```

### User-run commands

```bash
pytest tests/test_answer_type_classifier.py -q
```

---

## P3.T3 â€” Complexity detector

### Codex Prompt

DÃ¹ng prompt: `P3.T3`.

### Deliverables

```text
backend/query_analysis/complexity_detector.py
tests/test_complexity_detector.py
```

### Acceptance Criteria

```text
[ ] Detect single_hop.
[ ] Detect multi_hop vá»›i cÃ¡c cue: vá»«a, Ä‘á»“ng thá»i, sau Ä‘Ã³, trong khi.
[ ] Multiple domain signals cÃ³ thá»ƒ tÄƒng multi-hop score.
```

### User-run commands

```bash
pytest tests/test_complexity_detector.py -q
```

---

## P3.T4 â€” Legal entity extractor

### Codex Prompt

DÃ¹ng prompt: `P3.T4`.

### Deliverables

```text
backend/query_analysis/legal_entity_extractor.py
tests/test_legal_entity_extractor.py
```

### Acceptance Criteria

```text
[ ] Extract Äiá»u X.
[ ] Extract tÃªn/mÃ£ Luáº­t/Nghá»‹ Ä‘á»‹nh/ThÃ´ng tÆ° náº¿u cÃ³.
[ ] Extract tÃ i khoáº£n káº¿ toÃ¡n.
[ ] Extract ngÃ y/thÃ¡ng/nÄƒm/thá»i háº¡n.
[ ] Extract má»©c tiá»n pháº¡t.
```

### User-run commands

```bash
pytest tests/test_legal_entity_extractor.py -q
```

---

## P3.T5 â€” Query expander

### Codex Prompt

DÃ¹ng prompt: `P3.T5`.

### Deliverables

```text
backend/query_analysis/query_expander.py
tests/test_query_expander.py
```

### Acceptance Criteria

```text
[ ] DNNVV â†” doanh nghiá»‡p nhá» vÃ  vá»«a.
[ ] hÃ³a Ä‘Æ¡n Ä‘á» â†” hÃ³a Ä‘Æ¡n GTGT.
[ ] cho nghá»‰ viá»‡c â†” cháº¥m dá»©t há»£p Ä‘á»“ng lao Ä‘á»™ng.
[ ] tráº£ ná»£ trÆ°á»›c háº¡n â†” táº¥t toÃ¡n sá»›m.
[ ] Expansion khÃ´ng lÃ m máº¥t query gá»‘c.
```

### User-run commands

```bash
pytest tests/test_query_expander.py -q
```

---

## P3.T6 â€” Analyze questions orchestration

### Codex Prompt

DÃ¹ng prompt: `P3.T6`.

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
[ ] 2.000 cÃ¢u cÃ³ domain.
[ ] 2.000 cÃ¢u cÃ³ answer_type.
[ ] 2.000 cÃ¢u cÃ³ complexity.
[ ] CÃ³ legal_entities_json.
[ ] CÃ³ expanded_queries_json.
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

# Phase 4 â€” Hybrid Retrieval Baseline

## P4.T1 â€” BM25 retriever

### Codex Prompt

DÃ¹ng prompt: `P4.T1`.

### Deliverables

```text
backend/retrieval/bm25_retriever.py
```

### Acceptance Criteria

```text
[ ] search_legal_articles() thá»±c cháº¥t search trÃªn legal_article_chunks_bm25.
[ ] search_phapdien().
[ ] search_anle().
[ ] Return normalized RetrievalHit objects.
[ ] KhÃ´ng tráº£ raw OpenSearch response trá»±c tiáº¿p cho táº§ng trÃªn.
[ ] Legal BM25 hit pháº£i return canonical article_id.
[ ] chunk_id chá»‰ náº±m trong metadata.
[ ] Náº¿u nhiá»u chunk cÃ¹ng article_id, retriever hoáº·c fusion layer pháº£i dedup/group vá» article_id.
[ ] KhÃ´ng expose chunk_id nhÆ° citation id.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.bm25_retriever import BM25Retriever
r = BM25Retriever()
hits = r.search_legal_articles("doanh nghiá»‡p nhá» vÃ  vá»«a", top_k=5)
print(hits[:2])
PY
```

---
## P4.T2 â€” Dense retriever

### Codex Prompt

DÃ¹ng prompt: `P4.T2`.

### Deliverables

```text
backend/retrieval/dense_retriever.py
```

### Acceptance Criteria

```text
[ ] search_legal_articles_dense() thá»±c cháº¥t search trÃªn legal_article_chunks_dense.
[ ] search_phapdien_dense().
[ ] search_anle_dense().
[ ] DÃ¹ng VNLegalLALEmbedder.encode_query().
[ ] Return normalized RetrievalHit objects.
[ ] Legal dense hit pháº£i return canonical article_id.
[ ] chunk_id chá»‰ náº±m trong metadata.
[ ] Náº¿u nhiá»u chunk cÃ¹ng article_id, retriever hoáº·c fusion layer pháº£i dedup/group vá» article_id.
[ ] KhÃ´ng expose chunk_id nhÆ° citation id.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.dense_retriever import DenseRetriever
r = DenseRetriever()
hits = r.search_legal_articles_dense("doanh nghiá»‡p nhá» vÃ  vá»«a", top_k=5)
print(hits[:2])
PY
```

---
## P4.T3 â€” Exact retriever

### Codex Prompt

DÃ¹ng prompt: `P4.T3`.

### Note

- Runtime chÃ­nh dÃ¹ng exact_index.duckdb.
- exact_index.json chá»‰ legacy/debug náº¿u cÃ²n.
- Strong law_id_article_no match khÃ´ng append fallback article_no_only/law_id_only.

### Deliverables

```text
backend/retrieval/exact_retriever.py
```

### Acceptance Criteria

```text
[ ] Detect Äiá»u X trong question.
[ ] Detect mÃ£ vÄƒn báº£n náº¿u cÃ³.
[ ] Detect tÃ i khoáº£n káº¿ toÃ¡n náº¿u cÃ³.
[ ] Return canonical LegalArticle candidate IDs.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.exact_retriever import ExactRetriever
r = ExactRetriever("data/processed/exact_index.duckdb")
print(r.search("Theo Äiá»u 4 Luáº­t Há»— trá»£ DNNVV thÃ¬ sao?", top_k=5))
PY
```

---

## P4.T4 â€” Phapdien retriever + mapper

### Codex Prompt

DÃ¹ng prompt: `P4.T4`.

### Deliverables

```text
backend/retrieval/phapdien_retriever.py
```

### Acceptance Criteria

```text
[ ] Search phapdien BM25/dense hits.
[ ] Map phapdien_id sang legal_article_id báº±ng phapdien_to_vbpl_map.
[ ] KhÃ´ng return phapdien article_title lÃ m citation.
[ ] CÃ³ mapping_score trong output.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.phapdien_retriever import PhapdienMappedRetriever
r = PhapdienMappedRetriever()
hits = r.search_and_map("há»— trá»£ doanh nghiá»‡p nhá» vÃ  vá»«a", top_k=5)
print(hits[:2])
PY
```

---

## P4.T5 â€” RRF fusion

### Codex Prompt

DÃ¹ng prompt: `P4.T5`.

### Deliverables

```text
backend/retrieval/fusion.py
tests/test_fusion.py
```

### Acceptance Criteria

```text
[ ] reciprocal_rank_fusion() Ä‘Ãºng cÃ´ng thá»©c.
[ ] Merge duplicate article_id.
[ ] CÃ³ source contribution.
[ ] CÃ³ score_boost() tÃ¡ch riÃªng.
[ ] CÃ³ pytest cho RRF.
```

### User-run commands

```bash
pytest tests/test_fusion.py -q
```

---

## P4.T6 â€” Article selector

### Codex Prompt

DÃ¹ng prompt: `P4.T6`.

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
[ ] CÃ³ dedup.
[ ] KhÃ´ng chá»n article dÆ°á»›i threshold quÃ¡ tháº¥p náº¿u cÃ³ score.
```

### User-run commands

```bash
pytest tests/test_article_selector.py -q
```

---

## P4.T7 â€” Hybrid retrieval orchestrator

### Codex Prompt

DÃ¹ng prompt: `P4.T7`.

### Deliverables

```text
backend/retrieval/hybrid_retrieval.py
```

### Acceptance Criteria

```text
[ ] Gá»i BM25 legal.
[ ] Gá»i dense legal.
[ ] Gá»i exact.
[ ] Gá»i phapdien mapped.
[ ] RRF fusion.
[ ] Article selection.
[ ] Output selected canonical LegalArticle IDs.
[ ] KhÃ´ng dÃ¹ng LLM.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.hybrid_retrieval import HybridLegalRetriever
r = HybridLegalRetriever()
res = r.retrieve("Doanh nghiá»‡p nhá» vÃ  vá»«a Ä‘Æ°á»£c há»— trá»£ nhá»¯ng gÃ¬?")
print(res)
PY
```

---

## P4.T8 â€” Run retrieval script

### Codex Prompt

DÃ¹ng prompt: `P4.T8`.

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
[ ] Script Ä‘á»c test_questions_analyzed.parquet.
[ ] Ghi retrieval_results.jsonl.
[ ] Má»—i row cÃ³ id, question, selected_articles.
[ ] selected_articles chá»‰ chá»©a canonical article IDs.
[ ] CÃ³ logging tiáº¿n Ä‘á»™.
```

### User-run commands

```bash
python scripts/04_run_retrieval.py
head -n 3 data/outputs/retrieval_results.jsonl
```

---

# Phase 5 â€” QA Generation + Submission

## P5.T1 â€” LLM client

### Codex Prompt

DÃ¹ng prompt: `P5.T1`.

### Deliverables

```text
backend/infrastructure/gen_llm_models/vllm_client.py
backend/infrastructure/gen_llm_models/qwen_client.py
```

### Acceptance Criteria

```text
[ ] Client configurable endpoint/model.
[ ] temperature default = 0.
[ ] CÃ³ timeout/retry cÆ¡ báº£n.
[ ] KhÃ´ng gá»i LLM á»Ÿ import-time.
```

### User-run commands

```bash
python - <<'PY'
from backend.infrastructure.gen_llm_models.vllm_client import VLLMClient
print("client import ok")
PY
```

---

## P5.T2 â€” Answer templates + prompt

### Codex Prompt

DÃ¹ng prompt: `P5.T2`.

### Deliverables

```text
backend/qa/answer_templates.py
backend/prompts/legal_qa_prompt.txt
```

### Acceptance Criteria

```text
[ ] CÃ³ template general.
[ ] CÃ³ template deadline.
[ ] CÃ³ template sanction.
[ ] CÃ³ template procedure/dossier.
[ ] CÃ³ template yes_no.
[ ] Prompt yÃªu cáº§u chá»‰ dÃ¹ng selected_articles.
[ ] Prompt yÃªu cáº§u nháº¯c Äiá»u X.
```

### User-run commands

```bash
python - <<'PY'
from backend.qa.answer_templates import build_answer_prompt
print(build_answer_prompt(question="CÃ¢u há»i test", articles=[], answer_type="general")[:500])
PY
```

---

## P5.T3 â€” Answer generator

### Codex Prompt

DÃ¹ng prompt: `P5.T3`.

### Deliverables

```text
backend/qa/answer_generator.py
```

### Acceptance Criteria

```text
[ ] Input gá»“m question, selected_articles, answer_type.
[ ] Build context tá»« selected_articles.
[ ] Gá»i LLM client.
[ ] KhÃ´ng sinh relevant_docs/relevant_articles.
[ ] CÃ³ fallback náº¿u selected_articles rá»—ng.
```

### User-run commands

```bash
python - <<'PY'
from backend.qa.answer_generator import AnswerGenerator
print("answer generator import ok")
PY
```

---

## P5.T4 â€” Citation postprocess

### Codex Prompt

DÃ¹ng prompt: `P5.T4`.

### Deliverables

```text
backend/qa/citation_postprocess.py
tests/test_citation_postprocess.py
```

### Acceptance Criteria

```text
[ ] Kiá»ƒm tra answer cÃ³ nháº¯c Äiá»u X Ä‘Ã£ chá»n.
[ ] Append "CÄƒn cá»© phÃ¡p lÃ½" náº¿u thiáº¿u.
[ ] KhÃ´ng thÃªm Äiá»u ngoÃ i selected_articles.
[ ] CÃ³ pytest.
```

### User-run commands

```bash
pytest tests/test_citation_postprocess.py -q
```

---

## P5.T5 â€” Submission builder

### Codex Prompt

DÃ¹ng prompt: `P5.T5`.

### Deliverables

```text
backend/submission/build_results.py
backend/submission/validate_results.py
backend/submission/make_zip.py
tests/test_submission_validation.py
```

### Acceptance Criteria

```text
[ ] results.json lÃ  JSON list.
[ ] Má»—i item cÃ³ id, question, answer, relevant_docs, relevant_articles.
[ ] relevant_docs derive tá»« selected_articles.
[ ] relevant_articles derive tá»« canonical LegalArticle.
[ ] Validate duplicate id.
[ ] Validate format relevant_docs.
[ ] Validate format relevant_articles.
[ ] Zip chá»‰ chá»©a results.json á»Ÿ root.
```

### User-run commands

```bash
pytest tests/test_submission_validation.py -q
```

---

## P5.T6 â€” QA + submission scripts

### Codex Prompt

DÃ¹ng prompt: `P5.T6`.

### Deliverables

```text
scripts/05_generate_answers.py
scripts/06_build_submission.py
scripts/07_validate_submission.py
```

### Acceptance Criteria

```text
[ ] generate_answers Ä‘á»c retrieval_results.jsonl.
[ ] build_submission táº¡o results.json.
[ ] validate_submission kiá»ƒm tra schema/format.
[ ] Scripts khÃ´ng chá»©a business logic lá»›n.
[ ] NgÆ°á»i dÃ¹ng tá»± cháº¡y scripts.
```

### User-run commands

```bash
python scripts/05_generate_answers.py
python scripts/06_build_submission.py
python scripts/07_validate_submission.py
ls -lh data/outputs/results.json data/outputs/submission.zip
```

---

# Phase 6 â€” Evaluation + Error Analysis

## P6.T1 â€” Metrics

### Codex Prompt

DÃ¹ng prompt: `P6.T1`.

### Deliverables

```text
backend/evaluation/metrics.py
tests/test_metrics.py
```

### Acceptance Criteria

```text
[ ] precision().
[ ] recall().
[ ] f2_score().
[ ] hit_at_k().
[ ] mrr().
[ ] CÃ³ pytest.
```

### User-run commands

```bash
pytest tests/test_metrics.py -q
```

---

## P6.T2 â€” Error analysis report

### Codex Prompt

DÃ¹ng prompt: `P6.T2`.

### Deliverables

```text
backend/evaluation/error_analysis.py
```

### Acceptance Criteria

```text
[ ] Táº¡o low_confidence_questions.csv.
[ ] Táº¡o retrieval_debug_report.csv.
[ ] CÃ³ error categories chuáº©n.
[ ] KhÃ´ng cáº§n labels váº«n táº¡o report mÃ´ táº£ Ä‘Æ°á»£c.
```

### User-run commands

```bash
python - <<'PY'
from backend.evaluation.error_analysis import build_error_analysis_report
print("error analysis import ok")
PY
```

## P6.R3 â€” Detect unsupported citations in generated answers

### Codex Prompt

DÃ¹ng prompt: `P6.R3`.

### Bá»‘i cáº£nh

Sau khi cháº¡y `generated_answers_v2_merged.jsonl`, há»‡ thá»‘ng Ä‘Ã£ xá»­ lÃ½ xong lá»—i `empty_article_text`, nhÆ°ng váº«n phÃ¡t hiá»‡n má»™t sá»‘ cÃ¢u tráº£ lá»i cÃ³ dáº¥u hiá»‡u LLM viá»‡n dáº«n Ä‘iá»u/vÄƒn báº£n khÃ´ng náº±m trong `selected_articles`.

VÃ­ dá»¥ lá»—i cáº§n báº¯t:

```text
Answer nháº¯c: Äiá»u 27, Nghá»‹ Ä‘á»‹nh 65/2023/NÄ-CP
NhÆ°ng selected_articles chá»‰ cÃ³ Äiá»u 31 vÃ  Äiá»u 95 cá»§a 65/2023/NÄ-CP
```

ÄÃ¢y lÃ  lá»—i cháº¥t lÆ°á»£ng quan trá»ng vÃ¬ validator hiá»‡n táº¡i má»›i kiá»ƒm tra schema/format, chÆ°a kiá»ƒm tra viá»‡c answer cÃ³ dÃ¹ng cÄƒn cá»© ngoÃ i context hay khÃ´ng.

### Deliverables

```text
backend/evaluation/unsupported_citations.py
tests/test_unsupported_citations.py
backend/evaluation/error_analysis.py
tests/test_error_analysis.py
```

### Acceptance Criteria

```text
[ ] CÃ³ hÃ m phÃ¡t hiá»‡n citation trong answer dáº¡ng Äiá»u X + mÃ£/tÃªn vÄƒn báº£n.
[ ] So sÃ¡nh citation Ä‘Æ°á»£c nháº¯c trong answer vá»›i selected_articles.
[ ] Náº¿u answer nháº¯c Äiá»u/VÄƒn báº£n khÃ´ng náº±m trong selected_articles thÃ¬ flag unsupported_citation_in_answer.
[ ] KhÃ´ng flag cÃ¡c citation yáº¿u chá»‰ cÃ³ â€œÄiá»u Xâ€ nhÆ°ng khÃ´ng cÃ³ mÃ£/tÃªn vÄƒn báº£n rÃµ rÃ ng, Ä‘á»ƒ trÃ¡nh false positive.
[ ] Táº¡o unsupported_citations_report.csv.
[ ] Bá»• sung unsupported_citation_in_answer vÃ o low_confidence_questions.csv.
[ ] Summary cá»§a build_error_analysis_report cÃ³ unsupported_citations_report_path.
[ ] KhÃ´ng gá»i LLM.
[ ] KhÃ´ng cháº¡y láº¡i retrieval.
[ ] KhÃ´ng sinh láº¡i QA.
[ ] KhÃ´ng sá»­a submission builder/validator.
[ ] CÃ³ pytest.
```

### User-run commands

```bash
pytest tests/test_unsupported_citations.py tests/test_error_analysis.py -q
```

```bash
python - <<'PY'
from backend.evaluation.error_analysis import build_error_analysis_report

summary = build_error_analysis_report(
retrieval_results_path="data/outputs/retrieval_results.jsonl",
generated_answers_path="data/outputs/generated_answers_v2_merged.jsonl",
output_dir="data/outputs/error_analysis_v2",
)
print(summary)
PY
```

```bash
python - <<'PY'
import pandas as pd
from pathlib import Path
from collections import Counter

path = Path("data/outputs/error_analysis_v2/low_confidence_questions.csv")
df = pd.read_csv(path)

counter = Counter()
for value in df["issue_categories"].fillna(""):
    for part in str(value).replace(";", ",").replace("|", ",").split(","):
        part = part.strip()
        if part:
            counter[part] += 1

print(counter.most_common(30))

report_path = Path("data/outputs/error_analysis_v2/unsupported_citations_report.csv")
if report_path.exists():
    report = pd.read_csv(report_path)
    print("unsupported_citations_report shape:", report.shape)
    print(report.head(20).to_string(index=False))
else:
    print("unsupported_citations_report.csv not found")
PY
```
---

# Phase 7 â€” Reranker / LLM Verifier

## P7.T1 â€” Reranker interface

### Codex Prompt

DÃ¹ng prompt: `P7.T1`.

### Deliverables

```text
backend/retrieval/reranker.py
```

### Acceptance Criteria

```text
[ ] CÃ³ base interface rerank(question, candidates).
[ ] CÃ³ no-op reranker fallback.
[ ] KhÃ´ng phÃ¡ baseline retrieval.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.reranker import NoOpReranker
print(NoOpReranker().rerank("q", []))
PY
```

---

## P7.T2 â€” LLM verifier

### Codex Prompt

DÃ¹ng prompt: `P7.T2`.

### Deliverables

```text
backend/retrieval/llm_verifier.py
backend/prompts/verifier_prompt.txt
```

### Acceptance Criteria

```text
[ ] Verifier output JSON parse Ä‘Æ°á»£c.
[ ] CÃ³ fallback khi JSON lá»—i.
[ ] KhÃ´ng dÃ¹ng verifier náº¿u chÆ°a báº­t config.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.llm_verifier import LLMVerifier
print("verifier import ok")
PY
```

---

# Phase 8 â€” Neo4j Graph Expansion

## P8.T1 â€” Neo4j client

### Codex Prompt

DÃ¹ng prompt: `P8.T1`.

### Deliverables

```text
backend/infrastructure/graph_store/neo4j_client.py
```

### Acceptance Criteria

```text
[ ] CÃ³ health_check().
[ ] CÃ³ run_read_query().
[ ] CÃ³ run_write_query().
[ ] KhÃ´ng connect á»Ÿ import-time.
```

### User-run commands

```bash
python - <<'PY'
from backend.infrastructure.graph_store.neo4j_client import Neo4jClient
print("neo4j client import ok")
PY
```

---

## P8.T2 â€” Build graph index

### Codex Prompt

DÃ¹ng prompt: `P8.T2`.

### Deliverables

```text
backend/indexing/build_graph_index.py
```

### Acceptance Criteria

```text
[ ] Táº¡o Law nodes.
[ ] Táº¡o Article nodes.
[ ] Táº¡o HAS_ARTICLE relationships.
[ ] Táº¡o PhapdienArticle nodes náº¿u cÃ³ mapping.
[ ] Táº¡o DERIVED_FROM relationships.
[ ] CÃ³ constraints Cypher.
```

### User-run commands

```bash
python - <<'PY'
from backend.indexing.build_graph_index import build_graph_index
print("graph builder import ok")
PY
```

---

## P8.T3 â€” Graph expander

### Codex Prompt

DÃ¹ng prompt: `P8.T3`.

### Deliverables

```text
backend/retrieval/graph_expander.py
```

### Acceptance Criteria

```text
[ ] Input candidate_article_ids.
[ ] Return neighbor_article_ids + graph_boost_scores.
[ ] KhÃ´ng add neighbor mÃ¹ quÃ¡ng.
[ ] CÃ³ max_neighbors config.
```

### User-run commands

```bash
python - <<'PY'
from backend.retrieval.graph_expander import GraphExpander
print("graph expander import ok")
PY
```

---

# Phase 9 â€” Fine-tuning Preparation

## P9.T1 â€” Reranker training data builder

### Codex Prompt

DÃ¹ng prompt: `P9.T1`.

### Deliverables

```text
backend/evaluation/build_reranker_training_data.py
```

### Acceptance Criteria

```text
[ ] Output query, positive_article_id, hard_negative_article_ids.
[ ] Hard negatives láº¥y tá»« retrieval logs.
[ ] KhÃ´ng fine-tune model trong task nÃ y.
[ ] CÃ³ validation article_id tá»“n táº¡i trong legal_articles.
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

## U1 â€” End-to-end baseline runner

### Codex Prompt

DÃ¹ng prompt: `U1`.

### Deliverables

```text
scripts/run_phase_1_to_5_baseline.py
```

### Acceptance Criteria

```text
[ ] Script gá»i láº§n lÆ°á»£t Phase 1 â†’ Phase 5.
[ ] CÃ³ logging start/end má»—i step.
[ ] Stop on failure.
[ ] KhÃ´ng duplicate business logic.
[ ] NgÆ°á»i dÃ¹ng tá»± cháº¡y.
```

### User-run commands

```bash
python scripts/run_phase_1_to_5_baseline.py
```

---

## U2 â€” Debug retrieval for one question

### Codex Prompt

DÃ¹ng prompt: `U2`.

### Deliverables

```text
scripts/debug_retrieval_for_question.py
```

### Acceptance Criteria

```text
[ ] CÃ³ arg --id.
[ ] In question/domain/answer_type/complexity.
[ ] In BM25 hits.
[ ] In dense hits.
[ ] In exact hits.
[ ] In phapdien hits vÃ  mapped articles.
[ ] In RRF merged candidates.
[ ] In selected final articles.
[ ] KhÃ´ng generate answer.
```

### User-run commands

```bash
python scripts/debug_retrieval_for_question.py --id 1
```

---

# Definition of Done chung

Má»™t task chá»‰ Ä‘Æ°á»£c coi lÃ  xong khi:

```text
[ ] Deliverables Ä‘Ã£ táº¡o/sá»­a Ä‘Ãºng file.
[ ] Acceptance Criteria Ä‘Æ°á»£c Codex checklist láº¡i.
[ ] CÃ³ lá»‡nh test/validation Ä‘á»ƒ ngÆ°á»i dÃ¹ng cháº¡y.
[ ] KhÃ´ng cÃ³ logic vÆ°á»£t scope task.
[ ] KhÃ´ng hard-code path.
[ ] KhÃ´ng tá»± cháº¡y lá»‡nh thay ngÆ°á»i dÃ¹ng.
[ ] Náº¿u cÃ³ test, pytest tÆ°Æ¡ng á»©ng pass khi ngÆ°á»i dÃ¹ng cháº¡y.
```
## Workflow váº­n hÃ nh tá»« Phase 3 trá»Ÿ Ä‘i

- MÃ´i trÆ°á»ng code chÃ­nh: mÃ¡y Windows local.
- MÃ´i trÆ°á»ng cháº¡y náº·ng: GX10.
- Codex thá»±c hiá»‡n code/edit/test unit nháº¹ trÃªn Windows; ngÆ°á»i dÃ¹ng tá»± cháº¡y cÃ¡c lá»‡nh validate náº·ng trÃªn GX10 vÃ  gá»­i log láº¡i.
- Quy trÃ¬nh khuyáº¿n nghá»‹:
  1. Code trÃªn Windows.
  2. Cháº¡y unit test nháº¹ trÃªn Windows náº¿u phÃ¹ há»£p.
  3. Commit/push lÃªn branch lÃ m viá»‡c.
  4. GX10 `git pull`.
  5. GX10 cháº¡y smoke/full validation vá»›i dá»¯ liá»‡u vÃ  index tháº­t.
- KhÃ´ng commit generated artifacts tá»« GX10:
  - `data/processed/exact_index.duckdb`
  - `data/processed/exact_index.json`
  - Qdrant/OpenSearch volumes/data
  - cache, logs, temporary outputs
- Dense/vector jobs trÃªn GX10 nÃªn cháº¡y trong NVIDIA PyTorch container. BM25 vÃ  exact DuckDB cÃ³ thá»ƒ cháº¡y ngoÃ i container náº¿u dependency Ä‘áº§y Ä‘á»§.
- Phase 3+ pháº£i tÃ¡ch rÃµ code change vÃ  runtime validation: bÃ¡o cÃ¡o cuá»‘i cáº§n ghi lá»‡nh GX10 cáº§n cháº¡y, expected output, vÃ  tráº¡ng thÃ¡i pass/fail dá»±a trÃªn log ngÆ°á»i dÃ¹ng cung cáº¥p.


