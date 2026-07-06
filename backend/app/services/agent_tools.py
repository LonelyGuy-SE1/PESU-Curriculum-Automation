from collections.abc import Callable
from dataclasses import dataclass

from app.services.curriculum import draft_record, load_agent_draft, load_document_draft, ordered_courses, refined_course
from app.services.diffing import diff_course
from app.supabase import supabase

ToolHandler = Callable[[dict], dict]


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    parameters: dict
    handler: ToolHandler

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def list_tool_schemas() -> list[dict]:
    return [tool.schema() for tool in TOOLS.values()]


def call_tool(name: str, arguments: dict | None = None) -> dict:
    tool = TOOLS.get(name)
    if not tool:
        raise LookupError("Agent tool not found")
    return tool.handler(arguments or {})


def _require_int(arguments: dict, key: str) -> int:
    value = arguments.get(key)
    if value is None:
        raise ValueError(f"{key} is required")
    return int(value)


def _require_dict(arguments: dict, key: str) -> dict:
    value = arguments.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _get_current_course(arguments: dict) -> dict:
    return {"course": refined_course(_require_int(arguments, "refined_id"))}


def _diff_course_json(arguments: dict) -> dict:
    return diff_course(_require_dict(arguments, "current"), _require_dict(arguments, "proposed"))


def _create_course_draft(arguments: dict) -> dict:
    record = draft_record(
        _require_int(arguments, "refined_id"),
        _require_dict(arguments, "fields"),
        str(arguments.get("reason") or ""),
    )
    draft = supabase.table("agent_drafts").insert(record).execute().data[0]
    return {"draft": draft}


def _get_curriculum_json(arguments: dict) -> dict:
    query = supabase.table("refined_submissions").select("*").neq("status", "archived")
    if arguments.get("semester") is not None:
        query = query.eq("semester", int(arguments["semester"]))
    return {"courses": ordered_courses(query.execute().data)}


def _create_document_draft(arguments: dict) -> dict:
    courses = arguments.get("courses")
    if not isinstance(courses, list) or not courses:
        raise ValueError("courses must be a non-empty array")

    records = []
    for course in courses:
        if not isinstance(course, dict):
            raise ValueError("each course must be an object")
        records.append(draft_record(int(course.get("refined_id")), _require_dict(course, "fields"), str(arguments.get("reason") or "")))

    summaries = [record["diff_summary"] for record in records]
    document_summary = {
        "courses_changed": len(records),
        "courses_with_removed_topics": sum(1 for summary in summaries if summary.get("topics_removed")),
        "courses_with_protected_changes": sum(1 for summary in summaries if summary.get("protected_changes")),
        "max_syllabus_change_percent": max((summary.get("syllabus_change_percent") or 0 for summary in summaries), default=0),
    }
    document = (
        supabase.table("agent_document_drafts")
        .insert(
            {
                "curriculum_version_id": arguments.get("curriculum_version_id"),
                "uploaded_document_id": str(arguments.get("uploaded_document_id") or "").strip(),
                "diff_summary": document_summary,
                "change_reason": str(arguments.get("reason") or "").strip(),
                "status": "blocked" if document_summary["courses_with_protected_changes"] else "proposed",
            }
        )
        .execute()
        .data[0]
    )
    for record in records:
        record["document_draft_id"] = document["id"]
    drafts = supabase.table("agent_drafts").insert(records).execute().data
    return {"document_draft": document, "drafts": drafts}


def _get_course_draft(arguments: dict) -> dict:
    return {"draft": load_agent_draft(_require_int(arguments, "draft_id"))}


def _get_document_draft(arguments: dict) -> dict:
    return load_document_draft(_require_int(arguments, "document_draft_id"))


def _get_preview_url(arguments: dict) -> dict:
    kind = str(arguments.get("kind") or "")
    item_id = _require_int(arguments, "id")
    paths = {
        "course": f"/api/preview/course/{item_id}",
        "draft": f"/api/agent/drafts/{item_id}/preview",
        "document_draft": f"/api/agent/document-drafts/{item_id}/preview",
    }
    if kind not in paths:
        raise ValueError("kind must be course, draft, or document_draft")
    return {"url": paths[kind]}


def _list_courses(arguments: dict) -> dict:
    query = supabase.table("refined_submissions").select("id,semester,course_code,course_title").neq("status", "archived")
    if arguments.get("semester") is not None:
        query = query.eq("semester", int(arguments["semester"]))
    rows = query.execute().data
    rows.sort(key=lambda row: (int(row.get("semester") or 0), str(row.get("course_code") or ""), int(row.get("id") or 0)))
    return {"courses": rows}


def _attachment_text(arguments: dict) -> dict:
    session_id = _require_int(arguments, "session_id")
    ids = [int(value) for value in arguments.get("attachment_ids") or []]
    if not ids:
        raise ValueError("attachment_ids is required")
    rows = (
        supabase.table("chat_attachments")
        .select("id,filename,status,error,extracted_text")
        .eq("session_id", session_id)
        .in_("id", ids)
        .execute()
        .data
    )
    return {"attachments": rows}


OBJECT = {"type": "object", "additionalProperties": False}

TOOLS: dict[str, AgentTool] = {
    "get_current_course_json": AgentTool(
        "get_current_course_json",
        "Read the current template-ready JSON for one refined course.",
        {**OBJECT, "properties": {"refined_id": {"type": "integer"}}, "required": ["refined_id"]},
        _get_current_course,
    ),
    "diff_course_json": AgentTool(
        "diff_course_json",
        "Compare two course JSON objects and return patch operations, changed percent, and syllabus topic changes.",
        {**OBJECT, "properties": {"current": {"type": "object"}, "proposed": {"type": "object"}}, "required": ["current", "proposed"]},
        _diff_course_json,
    ),
    "create_course_draft": AgentTool(
        "create_course_draft",
        "Create a human-reviewable draft for one course. This never applies changes to refined_submissions.",
        {
            **OBJECT,
            "properties": {
                "refined_id": {"type": "integer"},
                "fields": {"type": "object"},
                "reason": {"type": "string"},
            },
            "required": ["refined_id", "fields"],
        },
        _create_course_draft,
    ),
    "get_curriculum_json": AgentTool(
        "get_curriculum_json",
        "Read template-ready JSON for the full curriculum, optionally filtered by semester.",
        {**OBJECT, "properties": {"semester": {"type": "integer", "minimum": 1, "maximum": 8}}},
        _get_curriculum_json,
    ),
    "create_document_draft": AgentTool(
        "create_document_draft",
        "Create one human-reviewable document draft containing proposed changes for multiple courses. This never applies changes.",
        {
            **OBJECT,
            "properties": {
                "courses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"refined_id": {"type": "integer"}, "fields": {"type": "object"}},
                        "required": ["refined_id", "fields"],
                        "additionalProperties": False,
                    },
                },
                "reason": {"type": "string"},
                "uploaded_document_id": {"type": "string"},
                "curriculum_version_id": {"type": "integer"},
            },
            "required": ["courses"],
        },
        _create_document_draft,
    ),
    "get_course_draft": AgentTool(
        "get_course_draft",
        "Read one staged course draft and its diff summary.",
        {**OBJECT, "properties": {"draft_id": {"type": "integer"}}, "required": ["draft_id"]},
        _get_course_draft,
    ),
    "get_document_draft": AgentTool(
        "get_document_draft",
        "Read one staged document draft and all linked course drafts.",
        {**OBJECT, "properties": {"document_draft_id": {"type": "integer"}}, "required": ["document_draft_id"]},
        _get_document_draft,
    ),
    "get_preview_url": AgentTool(
        "get_preview_url",
        "Return the preview URL for a course, course draft, or document draft.",
        {
            **OBJECT,
            "properties": {
                "kind": {"type": "string", "enum": ["course", "draft", "document_draft"]},
                "id": {"type": "integer"},
            },
            "required": ["kind", "id"],
        },
        _get_preview_url,
    ),
    "list_courses": AgentTool(
        "list_courses",
        "List refined course IDs and titles, optionally filtered by semester.",
        {**OBJECT, "properties": {"semester": {"type": "integer", "minimum": 1, "maximum": 8}}},
        _list_courses,
    ),
    "get_attachment_text": AgentTool(
        "get_attachment_text",
        "Read extracted text for uploaded chat attachments within a chat session.",
        {
            **OBJECT,
            "properties": {
                "session_id": {"type": "integer"},
                "attachment_ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["session_id", "attachment_ids"],
        },
        _attachment_text,
    ),
}
