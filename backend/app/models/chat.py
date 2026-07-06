from pydantic import BaseModel, Field, field_validator


class ChatSessionPayload(BaseModel):
    refined_id: int | None = None
    document_draft_id: int | None = None
    title: str = ""


class ChatSessionTitlePayload(BaseModel):
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value):
        return value.strip() if isinstance(value, str) else value


class ChatMessagePayload(BaseModel):
    content: str = ""
    metadata: dict = Field(default_factory=dict)

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value):
        return value.strip() if isinstance(value, str) else value
