# Skill: Canonical Legal Article Registry

## Goal

Build the single source of truth for all official legal citations.

## Main File

```text
data/processed/legal_articles.parquet
```

## Schema

Each row must contain:

- `article_id`
- `law_id`
- `law_title`
- `article_no`
- `article_title`
- `article_text`
- `source_url`
- `domain`
- `status`

## article_id Format

```text
law_id|law_title|article_no
```

Example:

```text
04/2017/QH14|Luật 04/2017/QH14 Luật Hỗ trợ doanh nghiệp nhỏ và vừa|Điều 4
```

## Submission Rule

`relevant_articles` must be built only from `legal_articles.parquet`.

`relevant_docs` must be derived from `relevant_articles`.

## Do Not

- Do not let LLM generate legal citation strings.
- Do not use phapdien article title as official article number.
- Do not use anle as citation source for `relevant_articles`.

## Required Functions

Implement:

- `build_article_id(article)`
- `build_relevant_article_string(article)`
- `build_relevant_doc_string(article)`
- `deduplicate_articles(articles)`
- `validate_article_registry(df)`

## Quality Checks

Check:

- duplicate `article_id`
- missing `law_id`
- missing `law_title`
- missing `article_no`
- article text too short
- invalid article number pattern
