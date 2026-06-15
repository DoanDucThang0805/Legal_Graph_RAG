# Skill: Vietnamese Legal Text Normalization

## Goal

Normalize Vietnamese legal documents into consistent internal format.

## Must Normalize

- Unicode NFC
- whitespace
- newlines
- article numbers
- law IDs
- legal titles
- source URLs
- empty/null values

## Article Number Format

Always normalize article numbers to:

```text
Điều X
```

Examples:

```text
Điều 4.  → Điều 4
điều 04  → Điều 4
Điều 7a. → Điều 7a
```

## Law Title Format

Competition requires:

```text
Loại văn bản + Mã văn bản + Trích yếu
```

Example:

```text
Luật 04/2017/QH14 Luật Hỗ trợ doanh nghiệp nhỏ và vừa
```

## Important Rule

`law_title` used in submission must come from canonical registry, not from LLM output.

## Suggested Modules

```text
backend/knowledge_processing/normalize_text.py
backend/knowledge_processing/normalize_legal_doc.py
backend/knowledge_processing/extract_articles.py
```

## Validation

For each legal article, require:

- `article_id`
- `law_id`
- `law_title`
- `article_no`
- `article_text`

Skip or log invalid rows.
