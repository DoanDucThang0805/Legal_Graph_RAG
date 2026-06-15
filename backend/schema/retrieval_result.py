"""Schemas for normalized retrieval outputs."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RetrievalCandidate(BaseModel):
    """Canonical candidate passed between retrieval, fusion, and selection steps."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    article_id: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    bm25_score: float = 0.0
    dense_score: float = 0.0
    exact_score: float = 0.0
    graph_score: float = 0.0
    rerank_score: float = 0.0
    final_score: float = 0.0
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("article_id", "source")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("required text field must not be empty")
        return value


class RetrievalResult(BaseModel):
    """Selected canonical articles for one question."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    id: int = Field(..., ge=1)
    question: str = Field(..., min_length=1)
    candidates: list[RetrievalCandidate] = Field(default_factory=list)
    selected_article_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be empty")
        return value
