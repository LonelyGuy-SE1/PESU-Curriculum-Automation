from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from postgrest.exceptions import APIError

from app.models.agent import AgentDocumentDraftPayload, AgentDraftPayload, AgentToolPayload
from app.rendering import templates
from app.services.agent_tools import call_tool, list_tool_schemas
from app.services.curriculum import create_version_snapshot, draft_record, load_agent_draft, load_document_draft, selected_curriculum_year, update_refined_fields
from app.services.diffing import diff_course
from app.services.errors import database_http_exception
from app.supabase import supabase

router = APIRouter()


def _diff_text_field(old: str, new: str) -> dict | None:
    """Return diff for a simple text field if changed, else None."""
    if old == new:
        return None
    return {"kind": "text", "old": old or "", "new": new or ""}


def _generate_version_name(summary: dict, prefix: str = "apply") -> str:
    """Generate a conventional commit-style version name from diff summary."""
    parts = []
    change_pct = summary.get("change_percent") or 0
    syllabus_pct = summary.get("syllabus_change_percent") or 0
    topics_added = summary.get("topics_added") or []
    topics_removed = summary.get("topics_removed") or []
    protected = summary.get("protected_changes") or []

    if protected:
        parts.append("fix: protected fields modified")
    elif syllabus_pct > 20:
        parts.append(f"feat: major syllabus update ({syllabus_pct:.0f}% changed)")
    elif syllabus_pct > 5:
        parts.append(f"feat: syllabus changes ({syllabus_pct:.0f}% changed)")
    elif change_pct > 10:
        parts.append(f"chore: content updates ({change_pct:.0f}% changed)")
    elif topics_added:
        parts.append(f"feat: added {', '.join(topics_added[:2])}{'...' if len(topics_added) > 2 else ''}")
    elif topics_removed:
        parts.append(f"fix: removed {', '.join(topics_removed[:2])}{'...' if len(topics_removed) > 2 else ''}")
    else:
        parts.append(f"chore: minor updates ({change_pct:.0f}% changed)")

    return f"{prefix}: {parts[0]}"


def _diff_list_field(old: list, new: list) -> dict | None:
    """Return diff for a list field if changed, else None."""
    if old == new:
        return None
    old_set = set(old)
    new_set = set(new)
    return {
        "kind": "list",
        "removed": sorted(old_set - new_set),
        "added": sorted(new_set - old_set),
        "unchanged": sorted(old_set & new_set),
    }


def _diff_units_field(old_units: list, new_units: list) -> dict | None:
    """Return diff for units field if changed, else None."""
    if old_units == new_units:
        return None
    # Match units by title
    old_by_title = {u.get("title", ""): u for u in old_units if isinstance(u, dict)}
    new_by_title = {u.get("title", ""): u for u in new_units if isinstance(u, dict)}
    all_titles = sorted(set(old_by_title.keys()) | set(new_by_title.keys()))
    
    units_diff = []
    for title in all_titles:
        old_u = old_by_title.get(title)
        new_u = new_by_title.get(title)
        if old_u and not new_u:
            units_diff.append({"kind": "removed", "unit": old_u})
        elif new_u and not old_u:
            units_diff.append({"kind": "added", "unit": new_u})
        else:
            # Both exist - diff their fields
            unit_changes = {}
            for field in ("title", "content", "hours"):
                ov = old_u.get(field, "")
                nv = new_u.get(field, "")
                if ov != nv:
                    unit_changes[field] = {"old": ov, "new": nv}
            if unit_changes:
                units_diff.append({"kind": "changed", "unit": new_u, "changes": unit_changes})
            else:
                units_diff.append({"kind": "unchanged", "unit": new_u})
    return {"kind": "units", "units": units_diff}


def _build_course_diff(base: dict, proposed: dict) -> dict:
    """Build a structured diff for a course, suitable for template rendering."""
    diff = {
        "course_title": _diff_text_field(base.get("course_title", ""), proposed.get("course_title", "")),
        "course_code": _diff_text_field(base.get("course_code", ""), proposed.get("course_code", "")),
        "program": _diff_text_field(base.get("program", ""), proposed.get("program", "")),
        "lecture_hours": _diff_text_field(str(base.get("lecture_hours", "")), str(proposed.get("lecture_hours", ""))),
        "tutorial_hours": _diff_text_field(str(base.get("tutorial_hours", "")), str(proposed.get("tutorial_hours", ""))),
        "practical_hours": _diff_text_field(str(base.get("practical_hours", "")), str(proposed.get("practical_hours", ""))),
        "self_study": _diff_text_field(str(base.get("self_study", "")), str(proposed.get("self_study", ""))),
        "credits": _diff_text_field(str(base.get("credits", "")), str(proposed.get("credits", ""))),
        "course_type": _diff_text_field(base.get("course_type", ""), proposed.get("course_type", "")),
        "semester": _diff_text_field(str(base.get("semester", "")), str(proposed.get("semester", ""))),
        "tools_languages": _diff_text_field(base.get("tools_languages", ""), proposed.get("tools_languages", "")),
        "desirable_knowledge": _diff_text_field(base.get("desirable_knowledge", ""), proposed.get("desirable_knowledge", "")),
        "prelude": _diff_text_field(base.get("prelude", ""), proposed.get("prelude", "")),
        "objectives": _diff_list_field(base.get("objectives") or [], proposed.get("objectives") or []),
        "course_outcomes": _diff_list_field(base.get("course_outcomes") or [], proposed.get("course_outcomes") or []),
        "units": _diff_units_field(base.get("units") or [], proposed.get("units") or []),
        "lab_experiments": _diff_list_field(base.get("lab_experiments") or [], proposed.get("lab_experiments") or []),
        "text_books": _diff_list_field(base.get("text_books") or [], proposed.get("text_books") or []),
        "reference_books": _diff_list_field(base.get("reference_books") or [], proposed.get("reference_books") or []),
    }
    return diff


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


@router.get("/agent/drafts")
def list_agent_drafts():
    try:
        rows = supabase.table("agent_drafts").select("*").order("id", desc=True).limit(100).execute().data
    except APIError as exc:
        raise database_http_exception(exc) from exc
    return {
        "drafts": [
            {
                "id": row["id"],
                "refined_id": row["refined_id"],
                "status": row.get("status") or "",
                "course_title": (row.get("proposed_json") or {}).get("course_title") or "",
                "course_code": (row.get("proposed_json") or {}).get("course_code") or "",
                "change_reason": row.get("change_reason") or "",
                "created_at": row.get("created_at") or "",
            }
            for row in rows
        ]
    }


@router.get("/agent/drafts/{draft_id}")
def get_agent_draft(draft_id: int):
    try:
        return {"draft": load_agent_draft(draft_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except APIError as exc:
        raise database_http_exception(exc) from exc


@router.get("/agent/drafts/{draft_id}/preview")
def preview_agent_draft(draft_id: int, diff: bool = False, curriculum_year: str | None = Query(None)):
    try:
        draft = load_agent_draft(draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except APIError as exc:
        raise database_http_exception(exc) from exc

    if diff:
        base = dict(draft.get("base_refined_json") or {})
        proposed = dict(draft.get("proposed_json") or {})
        course_diff = _build_course_diff(base, proposed)
        html = templates.get_template("jinja_diff.html").render(
            base=base,
            proposed=proposed,
            course_diff=course_diff,
            curriculum_year=selected_curriculum_year(curriculum_year),
            asset_root="/",
        )
    else:
        html = templates.get_template("jinja_sample.html").render(course=draft["proposed_json"], curriculum_year=selected_curriculum_year(curriculum_year), asset_root="/")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


def _generate_version_name(summary: dict, action: str) -> str:
    """Generate a conventional-commit-style version name from diff summary."""
    parts = []
    if summary.get("syllabus_change_percent", 0) > 0:
        parts.append(f"syllabus:{summary['syllabus_change_percent']}%")
    if summary.get("topics_added"):
        parts.append(f"+{len(summary['topics_added'])} topics")
    if summary.get("topics_removed"):
        parts.append(f"-{len(summary['topics_removed'])} topics")
    if summary.get("protected_changes"):
        parts.append("protected-fields")
    if not parts:
        parts.append("updates")
    change_reason = summary.get("change_reason") or ""
    prefix = action.capitalize()
    if change_reason:
        short = change_reason[:60].strip()
        return f"{prefix}: {short} ({', '.join(parts)})"
    return f"{prefix}: {', '.join(parts)}"


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
        version_name = _generate_version_name(summary, "apply")
        version = create_version_snapshot(version_name)
    except APIError as exc:
        raise database_http_exception(exc) from exc
    return {"message": "Draft applied", "data": data, "version": version}


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


@router.get("/agent/document-drafts")
def list_agent_document_drafts():
    try:
        rows = supabase.table("agent_document_drafts").select("*").order("id", desc=True).limit(100).execute().data
    except APIError as exc:
        raise database_http_exception(exc) from exc
    return {
        "document_drafts": [
            {
                "id": row["id"],
                "status": row.get("status") or "",
                "uploaded_document_id": row.get("uploaded_document_id") or "",
                "change_reason": row.get("change_reason") or "",
                "created_at": row.get("created_at") or "",
            }
            for row in rows
        ]
    }


@router.post("/agent/document-drafts/{document_draft_id}/apply")
def apply_agent_document_draft(document_draft_id: int):
    try:
        result = load_document_draft(document_draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except APIError as exc:
        raise database_http_exception(exc) from exc

    document = result["document_draft"]
    drafts = result["drafts"]

    if document.get("status") != "proposed":
        raise HTTPException(status_code=400, detail="Only proposed document drafts can be applied")

    summary = document.get("diff_summary") or {}
    if summary.get("courses_with_protected_changes"):
        raise HTTPException(status_code=400, detail="Document draft contains protected field changes")

    applied = []
    for draft in drafts:
        if draft.get("status") != "proposed":
            continue
        try:
            supabase.table("course_revision_history").insert(
                {
                    "refined_id": draft["refined_id"],
                    "agent_draft_id": draft["id"],
                    "previous_json": draft["base_refined_json"],
                    "next_json": draft["proposed_json"],
                    "json_patch": draft["json_patch"],
                    "diff_summary": draft["diff_summary"],
                    "change_reason": draft.get("change_reason") or "",
                }
            ).execute()
            update_refined_fields(int(draft["refined_id"]), draft["proposed_json"])
            supabase.table("agent_drafts").update({"status": "applied"}).eq("id", draft["id"]).execute()
            applied.append(draft["id"])
        except APIError as exc:
            raise database_http_exception(exc) from exc

    supabase.table("agent_document_drafts").update({"status": "applied"}).eq("id", document_draft_id).execute()
    version_name = _generate_version_name(summary, "apply-multi")
    version = create_version_snapshot(version_name)

    return {"message": f"Applied {len(applied)} drafts", "applied_draft_ids": applied, "version": version}


@router.get("/agent/document-drafts/{document_draft_id}")
def get_agent_document_draft(document_draft_id: int):
    try:
        return load_document_draft(document_draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except APIError as exc:
        raise database_http_exception(exc) from exc


@router.get("/agent/document-drafts/{document_draft_id}/preview")
def preview_agent_document_draft(document_draft_id: int, diff: bool = False, curriculum_year: str | None = Query(None)):
    try:
        result = load_document_draft(document_draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except APIError as exc:
        raise database_http_exception(exc) from exc
    drafts = result["drafts"]
    if not drafts:
        raise HTTPException(status_code=404, detail="Document draft not found")

    if diff:
        course_diffs = []
        for child in drafts:
            base = dict(child.get("base_refined_json") or {})
            proposed = dict(child.get("proposed_json") or {})
            course_diff = _build_course_diff(base, proposed)
            course_diffs.append({"base": base, "proposed": proposed, "course_diff": course_diff})
        html = templates.get_template("jinja_diff.html").render(
            course_diffs=course_diffs,
            curriculum_year=selected_curriculum_year(curriculum_year),
            asset_root="/",
        )
    else:
        courses = sorted(
            (draft["proposed_json"] for draft in drafts),
            key=lambda course: (int(course.get("semester") or 0), str(course.get("course_code") or ""), str(course.get("course_title") or "")),
        )
        html = templates.get_template("jinja_sample.html").render(courses=courses, semester="", curriculum_year=selected_curriculum_year(curriculum_year), asset_root="/", show_summaries=True)
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@router.get("/agent/tools")
def get_agent_tools():
    return {"tools": list_tool_schemas()}


@router.get("/agent/context-length")
def get_context_length():
    from app.services.openrouter import context_length, MODEL
    return {"context_length": context_length(), "model": MODEL}


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
