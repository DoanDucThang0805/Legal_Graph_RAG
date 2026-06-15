"""Submission schemas for results.json."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SubmissionItem(BaseModel):
    """One item in the final competition results.json file."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    id: int = Field(..., ge=1)
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    relevant_docs: list[str] = Field(default_factory=list)
    relevant_articles: list[str] = Field(default_factory=list)

    @field_validator("question", "answer")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("required text field must not be empty")
        return value

    @field_validator("relevant_docs", "relevant_articles")
    @classmethod
    def validate_string_list(cls, values: list[str]) -> list[str]:
        for value in values:
            if not isinstance(value, str) or not value.strip():
                raise ValueError("citation lists must contain non-empty strings")
        return values
