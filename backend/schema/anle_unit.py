"""Court judgment auxiliary-source schema."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnleUnit(BaseModel):
    """Sentence or paragraph unit from anle data used only as auxiliary context."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    unit_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    case_id: str | None = None
    title: str | None = None
    source_url: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("unit_id", "text")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("required text field must not be empty")
        return value
