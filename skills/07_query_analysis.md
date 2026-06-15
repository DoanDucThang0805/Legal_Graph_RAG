# Skill: Query Analysis for Legal RAG

## Goal

Classify each test question before retrieval.

## Outputs

For each question, detect:

- domain
- answer_type
- complexity
- legal entities
- expanded queries
- sub-questions if multi-hop

## Domains

Use these domains:

- `sme_support`
- `tax_invoice`
- `labor_bhxh`
- `accounting`
- `ip_consumer_data`
- `business_registration`
- `commerce_contract`
- `credit_guarantee`
- `environment`
- `other`

## Answer Types

Use:

- `deadline`
- `amount`
- `sanction`
- `procedure`
- `dossier`
- `conditions`
- `obligations`
- `yes_no`
- `accounting_account`
- `definition`
- `multi_part`

## Complexity

Use:

- `single_hop`
- `multi_hop`

Detect multi-hop when question contains:

- `vừa`
- `đồng thời`
- `sau đó`
- `trong khi`
- multiple legal domains

## Required Modules

```text
backend/query_analysis/domain_router.py
backend/query_analysis/answer_type_classifier.py
backend/query_analysis/complexity_detector.py
backend/query_analysis/legal_entity_extractor.py
backend/query_analysis/query_decomposer.py
```

## Important Rule

Query analysis should boost retrieval, not restrict it too aggressively.
