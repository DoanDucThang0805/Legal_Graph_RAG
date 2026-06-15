# Skill: Evaluation and Error Analysis

## Goal

Create local tools to evaluate and debug retrieval quality.

## Metrics

Implement:

- Precision@k
- Recall@k
- F2
- MRR
- Hit@k
- selected article count statistics

## Logging

For each question, log:

- id
- question
- domain
- answer_type
- complexity
- BM25 hits
- dense hits
- exact hits
- phapdien hits
- selected_articles
- answer
- confidence
- failure_reason if any

## Error Categories

Use:

- `missing_corpus`
- `wrong_domain`
- `wrong_article`
- `right_article_low_rank`
- `phapdien_mapping_error`
- `too_many_articles`
- `too_few_articles`
- `answer_missing_citation`
- `multi_hop_missing_branch`
- `invalid_submission_format`

## Required Modules

```text
backend/evaluation/metrics.py
backend/evaluation/error_analysis.py
backend/evaluation/pseudo_dev_builder.py
```

## Important Rule

Do not fine-tune before analyzing errors.
