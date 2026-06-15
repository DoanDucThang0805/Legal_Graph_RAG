"""Schemas for input questions."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TestQuestion(BaseModel):
    """Question item from the competition test set."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    id: int = Field(..., ge=1)
    question: str = Field(..., min_length=1)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be empty")
        return value
