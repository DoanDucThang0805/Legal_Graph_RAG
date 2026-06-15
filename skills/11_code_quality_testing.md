# Skill: Code Quality and Testing

## Goal

Ensure the project is maintainable, testable, and easy to debug.

## Coding Rules

- Use Python 3.11+.
- Use type hints.
- Use Pydantic models for schemas.
- Use clear module boundaries.
- Write small functions.
- Add detailed Vietnamese comments for complex logic.
- Avoid global mutable state.
- Avoid hard-coded paths; use config.
- Use logging instead of print in production modules.

## Testing

Add tests for:

- text normalization
- article extraction
- law title normalization
- phapdien-to-vbpl mapping
- RRF fusion
- article selection
- submission validation

## Suggested Tools

- pytest
- ruff
- mypy optional
- pre-commit optional

## Project Commands

Implement scripts:

```bash
python scripts/01_build_corpus.py
python scripts/02_build_indexes.py
python scripts/03_run_retrieval.py
python scripts/04_generate_answers.py
python scripts/05_build_submission.py
python scripts/06_validate_submission.py
```

## Do Not

- Do not put business logic inside scripts.
- Scripts should only call backend modules.
- Do not silently swallow exceptions.
- Log invalid rows into debug files.
