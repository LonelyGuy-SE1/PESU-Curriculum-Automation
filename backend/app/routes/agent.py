from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from postgrest.exceptions import APIError

from app.models.agent import AgentDocumentDraftPayload, AgentDraftPayload, AgentToolPayload
from app.rendering import templates
from app.services.agent_tools import call_tool, list_tool_schemas
from app.services.curriculum import draft_record, load_agent_draft, load_document_draft, update_refined_fields
from app.services.diffing import diff_course
from app.services.errors import database_http_exception
from app.supabase import supabase

router = APIRouter()


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
        result = supabase.table("agent_drafts").insert(record).execute()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except APIError as exc:
        raise database_http_exception(exc) from exc
    return {"message": "Draft created", "draft": result.data[0]}


@router.get("/agent/drafts/{draft_id}")
def get_agent_draft(draft_id: int):
    try:
        return {"draft": load_agent_draft(draft_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except APIError as exc:
        raise database_http_exception(exc) from exc


@router.get("/agent/drafts/{draft_id}/preview")
def preview_agent_draft(draft_id: int):
    try:
        draft = load_agent_draft(draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except APIError as exc:
        raise database_http_exception(exc) from exc
    html = templates.get_template("jinja_sample.html").render(course=draft["proposed_json"], curriculum_year="2025-2026", asset_root="/")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@router.post("/agent/drafts/{draft_id}/apply")
def apply_agent_draft(draft_id: int):
    try:
        draft = load_agent_draft(draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except APIError as exc:
        raise database_http_exception(exc) from exc

    summary = draft.get("diff_summary") or {}
    if draft.get("status") != "proposed":
        raise HTTPException(status_code=400, detail="Only proposed drafts can be applied")
    if summary.get("protected_changes"):
        raise HTTPException(status_code=400, detail="Draft changes deterministic fields")

    try:
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
    except APIError as exc:
        raise database_http_exception(exc) from exc
    return {"message": "Draft applied", "data": data}


@router.post("/agent/document-drafts")
def create_agent_document_draft(payload: AgentDocumentDraftPayload):
    try:
        records = [draft_record(course.refined_id, course.fields, payload.reason) for course in payload.courses]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except APIError as exc:
        raise database_http_exception(exc) from exc

    summaries = [record["diff_summary"] for record in records]
    document_summary = {
        "courses_changed": len(records),
        "courses_with_removed_topics": sum(1 for summary in summaries if summary.get("topics_removed")),
        "courses_with_protected_changes": sum(1 for summary in summaries if summary.get("protected_changes")),
        "max_syllabus_change_percent": max((summary.get("syllabus_change_percent") or 0 for summary in summaries), default=0),
    }
    status = "blocked" if document_summary["courses_with_protected_changes"] else "proposed"

    try:
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
    except APIError as exc:
        raise database_http_exception(exc) from exc
    return {"message": "Document draft created", "document_draft": document, "drafts": drafts}


@router.get("/agent/document-drafts/{document_draft_id}")
def get_agent_document_draft(document_draft_id: int):
    try:
        return load_document_draft(document_draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except APIError as exc:
        raise database_http_exception(exc) from exc


@router.get("/agent/document-drafts/{document_draft_id}/preview")
def preview_agent_document_draft(document_draft_id: int):
    try:
        drafts = load_document_draft(document_draft_id)["drafts"]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except APIError as exc:
        raise database_http_exception(exc) from exc
    if not drafts:
        raise HTTPException(status_code=404, detail="Document draft not found")

    courses = sorted(
        (draft["proposed_json"] for draft in drafts),
        key=lambda course: (int(course.get("semester") or 0), str(course.get("course_code") or ""), str(course.get("course_title") or "")),
    )
    html = templates.get_template("jinja_sample.html").render(courses=courses, semester="", curriculum_year="2025-2026", asset_root="/")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


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
    except APIError as exc:
        raise database_http_exception(exc) from exc
