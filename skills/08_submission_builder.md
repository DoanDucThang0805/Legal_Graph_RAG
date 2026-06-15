# Skill: Competition Submission Builder

## Goal

Build valid `results.json` and `submission.zip`.

## Required Output Format

Each item:

```json
{
  "id": 1,
  "question": "...",
  "answer": "...",
  "relevant_docs": [
    "law_id|law_title"
  ],
  "relevant_articles": [
    "law_id|law_title|Điều X"
  ]
}
```

## Critical Rules

- File must be named `results.json`.
- Zip must contain only `results.json` at root.
- `relevant_docs` must be derived from `relevant_articles`.
- `relevant_articles` must come from canonical article registry.
- Answer must explicitly mention `Điều X`.
- Do not let LLM create citation strings.

## Required Modules

```text
backend/submission/build_results.py
backend/submission/validate_results.py
backend/submission/make_zip.py
```

## Validation Checks

Check:

- JSON is a list
- all ids are present
- no duplicate ids
- required fields exist
- `relevant_docs` format is valid
- `relevant_articles` format is valid
- each answer mentions at least one selected `Điều X`
- no nested folder in zip

## Post-processing

If answer does not mention selected articles, append:

```text
Căn cứ pháp lý:
- Điều X [Tên văn bản]
```
