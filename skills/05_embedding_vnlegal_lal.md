# Skill: vnlegal-lal Embedding

## Goal

Use `darklethelong/vnlegal-lal` as the main dense embedding model for Vietnamese legal retrieval.

## Important Rules

- Query must use instruction prefix.
- Documents must not use query instruction prefix.
- Output dimension is 1024.
- Do not mix embeddings from other models with different dimensions.
- Re-embed phapdien, vbpl legal articles, and anle with the same model.

## Query Prefix

Use:

```text
Instruct: Given a Vietnamese legal question, retrieve relevant legal passages that answer the question
Query:
```

## Indexes

Create Qdrant collections:

```text
legal_articles_dense
phapdien_articles_dense
anle_units_dense
```

## Embedding Text Format

For legal articles:

```text
Tên văn bản: {law_title}
Điều: {article_no}
Tiêu đề điều: {article_title}
Nội dung:
{article_text}
```

For phapdien:

```text
Chủ đề: {topic_title}
Đề mục: {subject_title}
Chương: {chapter_title}
Điều pháp điển: {article_title}
Nguồn gốc: {source_note_text}
Nội dung:
{content_text}
Liên quan:
{related_note_text}
```

## Required Modules

```text
backend/infrastructure/embedding_models/vnlegal_lal.py
backend/indexing/build_vector_index.py
backend/retrieval/dense_retriever.py
```

## Performance Notes

Use batching and cache embeddings to parquet or numpy.
