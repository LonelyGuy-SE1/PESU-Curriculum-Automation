import json
import logging

import sentry_sdk
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from postgrest.exceptions import APIError

from app.models.chat import ChatMessagePayload, ChatSessionPayload
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
    context = ""
    if session.get("refined_id"):
        course = refined_course(int(session["refined_id"]))
        context = stable_context({"active_course": course})
    elif session.get("document_draft_id"):
        context = stable_context(load_document_draft(int(session["document_draft_id"])))
    return f"""You are the PESU Curriculum Automation live editor assistant.
Be concise, practical, and specific to the active curriculum data.
You may help the user understand fields, compare drafts, and decide what to edit.
You must not claim that you directly changed the database or applied a draft.
When a user asks for an edit, explain the exact fields that should change and remind them to review the diff before applying.

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
            message = insert_chat_message(session_id, "assistant", "".join(answer).strip())
            yield sse("done", {"message_id": message["id"]})
        except OpenRouterError as exc:
            logger.warning("Chat model request failed for session %s: status=%s", session_id, exc.status_code)
            yield sse("error", {"message": exc.message})
        except Exception as exc:
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
