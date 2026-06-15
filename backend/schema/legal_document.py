"""Canonical legal document schema."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LegalDocument(BaseModel):
    """Document-level canonical legal source from VBPL or equivalent data."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    doc_id: str = Field(..., min_length=1)
    law_id: str = Field(..., min_length=1)
    law_type: str | None = None
    law_title: str = Field(..., min_length=1)
    normalized_title: str | None = None
    source_url: str | None = None
    markdown: str = Field(..., min_length=1)
    issue_date: str | None = None
    effective_date: str | None = None
    status: str | None = None
    legal_area: str | None = None

    @field_validator("doc_id", "law_id", "law_title", "markdown")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("required text field must not be empty")
        return value
