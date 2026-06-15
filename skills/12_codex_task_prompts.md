# Skill: Ready-to-use Codex Task Prompts

## 1. Build Project Skeleton

```text
Read context.md, skills/01_project_architecture.md, and skills/11_code_quality_testing.md.
Create the backend package structure for the Legal Graph RAG project.
Add __init__.py files, config placeholders, Pydantic schemas, and scripts.
Do not implement retrieval logic yet.
```

## 2. Implement Hugging Face Loaders

```text
Read context.md, skills/02_data_loading_huggingface.md, skills/03_legal_normalization.md, and skills/04_canonical_article_registry.md.
Implement loaders for phapdien, anle, vbpl, and local testset.
Save outputs as parquet under data/processed.
Use Polars, datasets, pathlib, and typed functions.
Add detailed Vietnamese comments.
```

## 3. Implement Canonical Article Extraction

```text
Read skills/03_legal_normalization.md and skills/04_canonical_article_registry.md.
Implement extract_articles.py that extracts Điều X from VBPL markdown into legal_articles.parquet.
Add validation and invalid-row logging.
```

## 4. Implement Embedding

```text
Read skills/05_embedding_vnlegal_lal.md.
Implement vnlegal_lal.py wrapper.
Support encode_query and encode_documents.
Use instruction prefix only for queries.
Normalize embeddings.
```

## 5. Implement Hybrid Retrieval

```text
Read skills/06_hybrid_retrieval.md and skills/07_query_analysis.md.
Implement BM25, dense, exact retrievers, RRF fusion, and article selector.
The final output must be canonical LegalArticle objects only.
```

## 6. Implement Submission Builder

```text
Read skills/08_submission_builder.md.
Implement build_results.py, validate_results.py, and make_zip.py.
Do not let LLM generate relevant_docs or relevant_articles.
```
