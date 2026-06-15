# Skill: Hybrid Legal Retrieval

## Goal

Implement strong Phase 1 retrieval for legal article selection.

## Retrieval Sources

Use:

1. BM25 legal articles
2. Dense legal articles
3. BM25 phapdien
4. Dense phapdien
5. Exact search
6. Optional anle auxiliary retrieval

## Default Retrieval Config

```yaml
legal_bm25_top_k: 80
legal_dense_top_k: 80
phapdien_bm25_top_k: 50
phapdien_dense_top_k: 50
exact_top_k: 30
rrf_k: 60
final_top_k_default: 7
```

## Pipeline

```text
Question
→ query analysis
→ multi-source retrieval
→ map phapdien hits to legal articles
→ RRF fusion
→ score boost
→ article selection
```

## Required Files

```text
backend/retrieval/bm25_retriever.py
backend/retrieval/dense_retriever.py
backend/retrieval/exact_retriever.py
backend/retrieval/phapdien_retriever.py
backend/retrieval/fusion.py
backend/retrieval/article_selector.py
backend/retrieval/hybrid_retrieval.py
```

## RRF Function

Implement reciprocal rank fusion.

## Important Rule

The output of hybrid retrieval must be canonical `LegalArticle` objects, not raw phapdien/anle rows.

## Score Boost

Apply soft boost for:

- exact article match
- exact law title match
- domain match
- answer type match
- phapdien mapped source
- same law neighbor article

Do not hard-filter domain unless user explicitly asks.
