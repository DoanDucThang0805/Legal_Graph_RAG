"""Canonical legal article schema."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LegalArticle(BaseModel):
    """Article-level canonical registry item used for citations and retrieval."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    article_id: str = Field(..., min_length=1)
    law_id: str = Field(..., min_length=1)
    law_title: str = Field(..., min_length=1)
    article_no: str = Field(..., min_length=1)
    article_title: str | None = None
    article_text: str = Field(..., min_length=1)
    source_url: str | None = None
    domain: str | None = None
    status: str | None = None

    @field_validator("article_id", "law_id", "law_title", "article_no", "article_text")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("required text field must not be empty")
        return value

    @property
    def relevant_article_string(self) -> str:
        return f"{self.law_id}|{self.law_title}|{self.article_no}"

    @property
    def relevant_doc_string(self) -> str:
        return f"{self.law_id}|{self.law_title}"
