import json
import logging

import sentry_sdk
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from postgrest.exceptions import APIError

from app.models.chat import ChatMessagePayload, ChatSessionPayload, ChatSessionTitlePayload
from app.services.agent_tools import call_tool, list_tool_schemas
from app.services.attachments import extract_text
from app.services.curriculum import load_document_draft, refined_course
from app.services.errors import database_http_exception
from app.services.openrouter import OpenRouterError, stream_chat
from app.supabase import first_row, supabase

router = APIRouter()
MAX_ATTACHMENT_CONTEXT = 12000
logger = logging.getLogger(__name__)


def load_chat_session(session_id: int) -> dict:
    try:
        row = first_row(supabase.table("chat_sessions").select("*").eq("id", session_id))
    except APIError as exc:
        raise database_http_exception(exc) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return row


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


def stable_context(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)[:12000]


def chat_system_prompt(session: dict) -> str:
    session_id = session.get("id")
    context = ""
    if session.get("refined_id"):
        course = refined_course(int(session["refined_id"]))
        context = stable_context({"active_session_id": session_id, "active_refined_id": session["refined_id"], "active_course": course})
    elif session.get("document_draft_id"):
        context = stable_context({"active_session_id": session_id, **load_document_draft(int(session["document_draft_id"]))})
    else:
        context = stable_context({"active_session_id": session_id})
    return f"""You are the PESU Curriculum Automation live editor assistant.
Be concise, practical, and specific to the active curriculum data.
Use tools when the user asks to inspect, compare, or change curriculum data.
When the user asks to change the active course, call create_course_draft with the active_refined_id, only the fields that should change, and a short reason.
When the user asks for changes across multiple courses or an uploaded document, inspect the curriculum or attachment text, then call create_document_draft with the affected courses.
When the user asks what changed, call diff_course_json or read the relevant draft before answering.
Create reviewable drafts without asking for extra confirmation when the requested change is clear. Human approval happens when the user applies the draft.
For broad document requests, use get_curriculum_json to inspect the whole syllabus before proposing edits.
Never apply a draft, never claim a draft was applied, and never claim the refined database was changed.
After creating a draft, tell the user to review the diff in the Review panel before applying it.
If the user asks for an unsafe or unclear edit, ask for the missing detail instead of guessing.
Do not change deterministic fields such as program, hours, credits, or course type.
Describe edits as reviewable drafts that a human can apply.

Active context:
{context or "No active course or document draft is selected."}"""


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


@router.post("/chat/sessions")
def create_chat_session(payload: ChatSessionPayload):
    record = {"refined_id": payload.refined_id, "document_draft_id": payload.document_draft_id, "title": payload.title.strip()}
    result = supabase.table("chat_sessions").insert(record).execute()
    return {"session": result.data[0]}


@router.get("/chat/sessions")
def list_chat_sessions(refined_id: int | None = None, document_draft_id: int | None = None):
    query = supabase.table("chat_sessions").select("*").eq("status", "active")
    if refined_id is not None:
        query = query.eq("refined_id", refined_id)
    if document_draft_id is not None:
        query = query.eq("document_draft_id", document_draft_id)
    rows = query.order("id", desc=True).limit(50).execute().data
    return {"sessions": rows}


@router.get("/chat/sessions/{session_id}/messages")
def get_chat_messages(session_id: int):
    load_chat_session(session_id)
    return {"messages": chat_messages(session_id)}


@router.delete("/chat/sessions/{session_id}")
def clear_chat_session(session_id: int):
    load_chat_session(session_id)
    supabase.table("chat_sessions").delete().eq("id", session_id).execute()
    return {"message": "Chat deleted"}


@router.patch("/chat/sessions/{session_id}")
def rename_chat_session(session_id: int, payload: ChatSessionTitlePayload):
    load_chat_session(session_id)
    row = supabase.table("chat_sessions").update({"title": payload.title}).eq("id", session_id).execute().data[0]
    return {"message": "Chat renamed", "session": row}


@router.post("/chat/sessions/{session_id}/messages")
def create_chat_message(session_id: int, payload: ChatMessagePayload):
    if not payload.content and not payload.metadata:
        raise HTTPException(status_code=400, detail="Message content is required")
    session = load_chat_session(session_id)
    user_message = insert_chat_message(session_id, "user", payload.content, payload.metadata)
    update_attachment_message(session_id, attachment_ids(payload.metadata), user_message["id"])

    def stream():
        answer = []
        tool_results = []

        def remember_tool_result(name: str, result: dict) -> None:
            tool_results.append({"name": name, "result": result})

        def flush_tool_results():
            while tool_results:
                item = tool_results.pop(0)
                draft = (item["result"] or {}).get("draft")
                document_draft = (item["result"] or {}).get("document_draft")
                if item["name"] == "create_course_draft" and draft:
                    yield sse("draft", {"draft": draft})
                if item["name"] == "create_document_draft" and document_draft:
                    yield sse("document_draft", {"document_draft": document_draft})

        try:
            yield sse("status", {"message": "Message saved"})
            rows = chat_messages(session_id)
            yield sse("status", {"message": "Loading context"})
            system = chat_system_prompt(session)
            yield sse("status", {"message": "Streaming response"})
            for token in stream_chat(system, model_messages(session_id, rows), list_tool_schemas(), call_tool, remember_tool_result):
                yield from flush_tool_results()
                answer.append(token)
                yield sse("token", {"text": token})
            yield from flush_tool_results()
            message = insert_chat_message(session_id, "assistant", "".join(answer).strip())
            yield sse("done", {"message_id": message["id"]})
        except OpenRouterError as exc:
            yield from flush_tool_results()
            logger.warning(
                "Chat model request failed for session %s: status=%s detail=%s",
                session_id,
                exc.status_code,
                exc.provider_message[:300],
            )
            yield sse("error", {"message": exc.message})
        except Exception as exc:
            yield from flush_tool_results()
            logger.exception("Chat stream failed for session %s", session_id)
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
