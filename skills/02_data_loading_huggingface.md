# Skill: Data Loading from Hugging Face

## Goal

Implement robust dataset loaders for:

- `tmquan/phapdien-moj-gov-vn`
- `tmquan/anle-toaan-gov-vn`
- `tmquan/vbpl-vn`
- local competition testset `R2AIStage1DATA.json`

## Loading Rules

Never index raw Hugging Face rows directly.

Always follow:

```text
Raw Dataset
→ Load
→ Normalize
→ Internal Schema
→ Processed Parquet
→ Indexing
```

## Expected Outputs

Create these files:

```text
data/processed/test_questions.parquet
data/processed/phapdien_articles.parquet
data/processed/anle_units.parquet
data/processed/legal_documents.parquet
data/processed/legal_articles.parquet
data/processed/phapdien_to_vbpl_map.parquet
```

## Dataset Roles

### phapdien

Use for retrieval recall.

Do not use phapdien article title directly as `relevant_articles`.

### vbpl

Use as canonical source for:

- `law_id`
- `law_title`
- `Điều X`
- `article_text`

### anle

Use only as auxiliary context for legal reasoning.

Do not use anle to produce official `relevant_articles`.

### testset

Input format:

```json
[
  {
    "id": 1,
    "question": "..."
  }
]
```

## Implementation Requirements

Create loader modules:

```text
backend/knowledge_processing/load_testset.py
backend/knowledge_processing/load_phapdien.py
backend/knowledge_processing/load_anle.py
backend/knowledge_processing/load_vbpl.py
backend/knowledge_processing/build_corpus.py
```

Use:

- `datasets`
- `polars`
- `pyarrow`
- `pydantic`
- `pathlib`

## Code Style

- Use typed functions.
- Add detailed Vietnamese comments for important logic.
- Validate missing fields.
- Save intermediate results to parquet.
- Make scripts idempotent.
