from pydantic import BaseModel, Field


class AgentDraftPayload(BaseModel):
    refined_id: int
    fields: dict
    reason: str = ""


class AgentDocumentCoursePayload(BaseModel):
    refined_id: int
    fields: dict


class AgentDocumentDraftPayload(BaseModel):
    courses: list[AgentDocumentCoursePayload] = Field(min_length=1)
    reason: str = ""
    curriculum_version_id: int | None = None
    uploaded_document_id: str = ""


class AgentToolPayload(BaseModel):
    arguments: dict = Field(default_factory=dict)
