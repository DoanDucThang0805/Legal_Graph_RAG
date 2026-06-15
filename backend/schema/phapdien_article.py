"""Phapdien retrieval-source schema."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PhapdienArticle(BaseModel):
    """Phapdien unit used for retrieval and later mapping to canonical articles."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    phapdien_id: str = Field(..., min_length=1)
    topic_title: str | None = None
    subject_title: str | None = None
    chapter_title: str | None = None
    article_title: str | None = None
    content_text: str = Field(..., min_length=1)
    source_note_text: str | None = None
    related_note_text: str | None = None
    source_url: str | None = None
    source_links_json: str | None = None

    @field_validator("phapdien_id", "content_text")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("required text field must not be empty")
        return value
