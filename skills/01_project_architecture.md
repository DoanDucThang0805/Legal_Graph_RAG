# Skill: Legal Graph RAG Project Architecture

## Goal

Build a Vietnamese Legal RAG system for a competition where the final submission must include:

- `id`
- `question`
- `answer`
- `relevant_docs`
- `relevant_articles`

The system must prioritize correct legal article retrieval over free-form generation.

## Core Principle

The LLM must never decide `relevant_docs` or `relevant_articles`.

Only the canonical `legal_articles` registry can produce:

- `law_id|law_title`
- `law_id|law_title|Điều X`

## Architecture

Use this pipeline:

```text
Load datasets
→ Normalize legal documents
→ Build canonical article registry
→ Build indexes
→ Analyze query
→ Hybrid retrieval
→ RRF fusion
→ Dynamic article selection
→ Answer generation
→ Citation post-processing
→ Submission validation
```

## Required Modules

Use these module groups:

```text
backend/config
backend/infrastructure
backend/schema
backend/knowledge_processing
backend/indexing
backend/query_analysis
backend/retrieval
backend/qa
backend/evaluation
backend/submission
scripts
```

## Do Not

- Do not put all logic into `hybrid_retrieval.py`.
- Do not index Hugging Face raw rows directly.
- Do not allow the LLM to invent legal citations.
- Do not build `relevant_articles` from phapdien or anle directly.
- Do not add Neo4j in Phase 1 unless explicitly requested.

## Phase Plan

### Phase 1

BM25 + dense retrieval + exact search + RRF + submission builder.

### Phase 2

Reranker and LLM verifier.

### Phase 3

Neo4j graph expansion.

### Phase 4

Fine-tuning based on error analysis.
