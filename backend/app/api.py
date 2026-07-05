import json
import re
from pathlib import Path
from typing import Literal

import sentry_sdk
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape
from pydantic import BaseModel, Field, field_validator
from weasyprint import HTML

from app.preview import build_course_preview
from app.services.attachments import extract_text
from app.services.agent_tools import call_tool, list_tool_schemas
from app.services.curriculum import attach_submissions, draft_record, load_agent_draft, load_document_draft, ordered_courses, refined_course, update_refined_fields
from app.services.diffing import diff_course
from app.services.openrouter import stream_chat
from app.services.refinement import refine
from app.supabase import supabase

router = APIRouter()
APP_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = APP_DIR.parent.parent / "frontend"
templates = Environment(loader=FileSystemLoader(APP_DIR / "templates"), autoescape=select_autoescape(["html", "xml"]))
URL_RE = re.compile(r"https?://[^\s<>()]+")
MAX_ATTACHMENT_CONTEXT = 12000


def linkify(value: str) -> Markup:
    text = str(value or "")
    parts = []
    last = 0
    for match in URL_RE.finditer(text):
        raw_url = match.group(0)
        url = raw_url.rstrip(".,;:)]}")
        trailing = raw_url[len(url) :]
        safe_url = escape(url)
        parts.append(escape(text[last : match.start()]))
        parts.append(Markup(f'<a class="resource-link" href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_url}</a>'))
        parts.append(escape(trailing))
        last = match.end()
    parts.append(escape(text[last:]))
    return Markup("".join(str(part) for part in parts))


templates.filters["linkify"] = linkify


class CourseSubmission(BaseModel):
    faculty_email: str = Field(min_length=3, max_length=254)
    course_title: str = Field(min_length=3, max_length=150)
    offering_department: Literal["MA", "CS", "UZ"]
    target_department: Literal["CSE", "ECE", "ME", "BT", "EEE", "AIML"]
    semester: Literal["1", "2", "3", "4", "5", "6", "7", "8"]
    credit_category: Literal["0", "2", "4", "5"]
    raw_course_content: str = Field(min_length=50)
    text_books: str = Field(min_length=5)
    reference_books: str = ""
    preferred_tools: str = ""

    @field_validator("faculty_email", "course_title", "raw_course_content", "text_books", "reference_books", "preferred_tools", mode="before")
    @classmethod
    def strip(cls, v):
        return v.strip() if isinstance(v, str) else v


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


class ChatSessionPayload(BaseModel):
    refined_id: int | None = None
    document_draft_id: int | None = None
    title: str = ""


class ChatMessagePayload(BaseModel):
    content: str = ""
    metadata: dict = Field(default_factory=dict)

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value):
        return value.strip() if isinstance(value, str) else value


class AgentToolPayload(BaseModel):
    arguments: dict = Field(default_factory=dict)


def load_chat_session(session_id: int) -> dict:
    result = supabase.table("chat_sessions").select("*").eq("id", session_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return result.data


def chat_messages(session_id: int) -> list[dict]:
    rows = supabase.table("chat_messages").select("*").eq("session_id", session_id).order("id").execute().data
    return rows[-24:]


def insert_chat_message(session_id: int, role: str, content: str, metadata: dict | None = None) -> dict:
    return (
        supabase.table("chat_messages")
        .insert({"session_id": session_id, "role": role, "content": content, "metadata": metadata or {}})
        .execute()
        .data[0]
    )


def update_attachment_message(session_id: int, attachment_ids: list[int], message_id: int) -> None:
    if attachment_ids:
        supabase.table("chat_attachments").update({"message_id": message_id}).eq("session_id", session_id).in_("id", attachment_ids).execute()


def attachment_ids(metadata: dict | None) -> list[int]:
    ids = []
    for item in (metadata or {}).get("attachments") or []:
        if isinstance(item, dict) and item.get("id"):
            ids.append(int(item["id"]))
    return ids


def attachment_context(session_id: int, metadata: dict | None) -> str:
    ids = attachment_ids(metadata)
    if not ids:
        return ""
    rows = supabase.table("chat_attachments").select("filename,status,error,extracted_text").eq("session_id", session_id).in_("id", ids).execute().data
    blocks = []
    for row in rows:
        name = row.get("filename") or "attachment"
        status = row.get("status") or ""
        text = str(row.get("extracted_text") or "").strip()
        if text:
            blocks.append(f"Attachment: {name}\n{text[:MAX_ATTACHMENT_CONTEXT]}")
        else:
            error = row.get("error") or "No extracted text"
            blocks.append(f"Attachment: {name}\nStatus: {status}. {error}")
    return "\n\n".join(blocks)


def chat_system_prompt(session: dict) -> str:
    context = ""
    if session.get("refined_id"):
        course = refined_course(int(session["refined_id"]))
        context = stable_context({"active_course": course})
    elif session.get("document_draft_id"):
        draft = load_document_draft(int(session["document_draft_id"]))
        context = stable_context(draft)
    return f"""You are the PESU Curriculum Automation live editor assistant.
Be concise, practical, and specific to the active curriculum data.
You may help the user understand fields, compare drafts, and decide what to edit.
You must not claim that you directly changed the database or applied a draft.
When a user asks for an edit, explain the exact fields that should change and remind them to review the diff before applying.

Active context:
{context or "No active course or document draft is selected."}"""


def stable_context(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)[:12000]


def model_messages(session_id: int, rows: list[dict]) -> list[dict]:
    messages = []
    for row in rows:
        if row.get("role") not in {"user", "assistant"}:
            continue
        content = str(row.get("content") or "").strip()
        context = attachment_context(session_id, row.get("metadata")) if row.get("role") == "user" else ""
        if context:
            content = f"{content}\n\n{context}".strip()
        if content:
            messages.append({"role": row["role"], "content": content})
    return messages


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def refine_later(submission_id: int) -> None:
    try:
        refine(submission_id)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        supabase.table("submissions").update({"status": "refine_failed"}).eq("id", submission_id).execute()


@router.post("/submissions")
def receive(data: CourseSubmission, background_tasks: BackgroundTasks):
    payload = data.model_dump()
    payload["status"] = "pending"
    result = supabase.table("submissions").insert(payload).execute()
    submission = result.data[0]
    background_tasks.add_task(refine_later, submission["id"])
    return {"message": "Submission Received!", "submission": submission}


@router.get("/preview/semester/{sem}/courses")
def list_courses(sem: int):
    result = supabase.table("refined_submissions").select("id").eq("semester", sem).order("id").execute()
    return {"course_ids": [row["id"] for row in result.data]}


@router.get("/preview/courses")
def list_all_courses():
    result = supabase.table("refined_submissions").select("id,semester,course_code").execute()
    rows = sorted(result.data, key=lambda row: (int(row.get("semester") or 0), str(row.get("course_code") or ""), int(row.get("id") or 0)))
    return {"course_ids": [row["id"] for row in rows]}


@router.get("/preview/course/{refined_id}")
def preview_course(refined_id: int):
    result = supabase.table("refined_submissions").select("*").eq("id", refined_id).single().execute()
    row = attach_submissions([result.data])[0]
    html = templates.get_template("jinja_sample.html").render(
        course=build_course_preview(row),
        curriculum_year="2025-2026",
        asset_root="/",
    )
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@router.get("/preview/pdf")
def download_all_pdf(download: bool = Query(False)):
    result = supabase.table("refined_submissions").select("*").execute()
    courses = ordered_courses(result.data)
    html = templates.get_template("jinja_sample.html").render(courses=courses, semester="", curriculum_year="2025-2026", asset_root="")
    pdf = HTML(string=html, base_url=str(FRONTEND_DIR)).write_pdf()
    disposition = "attachment" if download else "inline"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="curriculum-preview.pdf"', "Cache-Control": "no-store"},
    )


@router.get("/preview/semester/{sem}/pdf")
def download_pdf(sem: int, download: bool = Query(False)):
    result = supabase.table("refined_submissions").select("*").eq("semester", sem).order("id").execute()
    courses = ordered_courses(result.data)
    html = templates.get_template("jinja_sample.html").render(courses=courses, semester=sem, curriculum_year="2025-2026", asset_root="")
    pdf = HTML(string=html, base_url=str(FRONTEND_DIR)).write_pdf()
    disposition = "attachment" if download else "inline"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="semester-{sem}.pdf"', "Cache-Control": "no-store"},
    )


@router.post("/submissions/{id}/refine")
def refine_submission(id: int):
    return {"message": "Refined", "data": refine(id)}


@router.get("/refined/{refined_id}")
def get_refined(refined_id: int):
    result = supabase.table("refined_submissions").select("*").eq("id", refined_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Refined submission not found")
    row = attach_submissions([result.data])[0]
    return {"id": refined_id, "fields": build_course_preview(row)}


@router.patch("/refined/{refined_id}")
def update_refined(refined_id: int, payload: dict):
    fields = payload.get("fields")
    if not isinstance(fields, dict):
        raise HTTPException(status_code=400, detail="fields is required")
    return {"message": "Updated", "data": update_refined_fields(refined_id, fields)}


@router.post("/agent/diff")
def compare_course(payload: dict):
    current = payload.get("current")
    proposed = payload.get("proposed")
    if not isinstance(current, dict) or not isinstance(proposed, dict):
        raise HTTPException(status_code=400, detail="current and proposed are required")
    return diff_course(current, proposed)


@router.post("/agent/drafts")
def create_agent_draft(payload: AgentDraftPayload):
    try:
        record = draft_record(payload.refined_id, payload.fields, payload.reason)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = supabase.table("agent_drafts").insert(record).execute()
    draft = result.data[0]
    return {"message": "Draft created", "draft": draft}


@router.get("/agent/drafts/{draft_id}")
def get_agent_draft(draft_id: int):
    try:
        return {"draft": load_agent_draft(draft_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/agent/drafts/{draft_id}/preview")
def preview_agent_draft(draft_id: int):
    try:
        draft = load_agent_draft(draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    html = templates.get_template("jinja_sample.html").render(
        course=draft["proposed_json"],
        curriculum_year="2025-2026",
        asset_root="/",
    )
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@router.post("/agent/drafts/{draft_id}/apply")
def apply_agent_draft(draft_id: int):
    try:
        draft = load_agent_draft(draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    summary = draft.get("diff_summary") or {}
    if draft.get("status") != "proposed":
        raise HTTPException(status_code=400, detail="Only proposed drafts can be applied")
    if summary.get("protected_changes"):
        raise HTTPException(status_code=400, detail="Draft changes deterministic fields")
    supabase.table("course_revision_history").insert(
        {
            "refined_id": draft["refined_id"],
            "agent_draft_id": draft_id,
            "previous_json": draft["base_refined_json"],
            "next_json": draft["proposed_json"],
            "json_patch": draft["json_patch"],
            "diff_summary": summary,
            "change_reason": draft.get("change_reason") or "",
        }
    ).execute()
    data = update_refined_fields(int(draft["refined_id"]), draft["proposed_json"])
    supabase.table("agent_drafts").update({"status": "applied"}).eq("id", draft_id).execute()
    return {"message": "Draft applied", "data": data}


@router.post("/agent/document-drafts")
def create_agent_document_draft(payload: AgentDocumentDraftPayload):
    try:
        records = [draft_record(course.refined_id, course.fields, payload.reason) for course in payload.courses]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    summaries = [record["diff_summary"] for record in records]
    document_summary = {
        "courses_changed": len(records),
        "courses_with_removed_topics": sum(1 for summary in summaries if summary.get("topics_removed")),
        "courses_with_protected_changes": sum(1 for summary in summaries if summary.get("protected_changes")),
        "max_syllabus_change_percent": max((summary.get("syllabus_change_percent") or 0 for summary in summaries), default=0),
    }
    status = "blocked" if document_summary["courses_with_protected_changes"] else "proposed"
    document = (
        supabase.table("agent_document_drafts")
        .insert(
            {
                "curriculum_version_id": payload.curriculum_version_id,
                "uploaded_document_id": payload.uploaded_document_id.strip(),
                "diff_summary": document_summary,
                "change_reason": payload.reason.strip(),
                "status": status,
            }
        )
        .execute()
        .data[0]
    )
    for record in records:
        record["document_draft_id"] = document["id"]
    drafts = supabase.table("agent_drafts").insert(records).execute().data
    return {"message": "Document draft created", "document_draft": document, "drafts": drafts}


@router.get("/agent/document-drafts/{document_draft_id}")
def get_agent_document_draft(document_draft_id: int):
    try:
        return load_document_draft(document_draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/agent/document-drafts/{document_draft_id}/preview")
def preview_agent_document_draft(document_draft_id: int):
    try:
        drafts = load_document_draft(document_draft_id)["drafts"]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not drafts:
        raise HTTPException(status_code=404, detail="Document draft not found")
    courses = sorted(
        (draft["proposed_json"] for draft in drafts),
        key=lambda course: (int(course.get("semester") or 0), str(course.get("course_code") or ""), str(course.get("course_title") or "")),
    )
    html = templates.get_template("jinja_sample.html").render(
        courses=courses,
        semester="",
        curriculum_year="2025-2026",
        asset_root="/",
    )
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@router.post("/chat/sessions")
def create_chat_session(payload: ChatSessionPayload):
    record = {
        "refined_id": payload.refined_id,
        "document_draft_id": payload.document_draft_id,
        "title": payload.title.strip(),
    }
    result = supabase.table("chat_sessions").insert(record).execute()
    return {"session": result.data[0]}


@router.get("/chat/sessions/{session_id}/messages")
def get_chat_messages(session_id: int):
    load_chat_session(session_id)
    return {"messages": chat_messages(session_id)}


@router.post("/chat/sessions/{session_id}/messages")
def create_chat_message(session_id: int, payload: ChatMessagePayload):
    if not payload.content and not payload.metadata:
        raise HTTPException(status_code=400, detail="Message content is required")
    session = load_chat_session(session_id)
    user_message = insert_chat_message(session_id, "user", payload.content, payload.metadata)
    update_attachment_message(session_id, attachment_ids(payload.metadata), user_message["id"])

    def stream():
        answer = []
        try:
            yield sse("status", {"message": "Message saved"})
            rows = chat_messages(session_id)
            yield sse("status", {"message": "Loading context"})
            system = chat_system_prompt(session)
            yield sse("status", {"message": "Streaming response"})
            for token in stream_chat(system, model_messages(session_id, rows)):
                answer.append(token)
                yield sse("token", {"text": token})
            content = "".join(answer).strip()
            message = insert_chat_message(session_id, "assistant", content)
            yield sse("done", {"message_id": message["id"]})
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            yield sse("error", {"message": "An internal error occurred. Please try again later."})

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})


@router.post("/chat/sessions/{session_id}/attachments")
async def upload_chat_attachments(session_id: int, files: list[UploadFile] = File(...)):
    load_chat_session(session_id)
    attachments = []
    for file in files:
        data = await file.read()
        text, status, error = extract_text(file.filename or "attachment", file.content_type or "", data)
        row = (
            supabase.table("chat_attachments")
            .insert(
                {
                    "session_id": session_id,
                    "filename": file.filename or "attachment",
                    "content_type": file.content_type or "",
                    "size_bytes": len(data),
                    "extracted_text": text,
                    "status": status,
                    "error": error,
                }
            )
            .execute()
            .data[0]
        )
        attachments.append(
            {
                "id": row["id"],
                "name": row["filename"],
                "type": row["content_type"],
                "size": row["size_bytes"],
                "status": row["status"],
                "error": row["error"],
                "extracted_chars": len(row.get("extracted_text") or ""),
            }
        )
    return {"attachments": attachments}


@router.get("/agent/tools")
def get_agent_tools():
    return {"tools": list_tool_schemas()}


@router.post("/agent/tools/{tool_name}")
def run_agent_tool(tool_name: str, payload: AgentToolPayload):
    try:
        return {"name": tool_name, "result": call_tool(tool_name, payload.arguments)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
