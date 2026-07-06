from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from postgrest.exceptions import APIError

from app.preview import build_course_preview
from app.rendering import templates
from app.services.curriculum import attach_submissions, update_refined_fields
from app.services.diffing import diff_course
from app.services.errors import database_http_exception
from app.supabase import first_row, supabase

router = APIRouter()
CURRICULUM_YEAR = "2025-2026"


def _version(version_id: int) -> dict:
    row = first_row(supabase.table("curriculum_versions").select("*").eq("id", version_id))
    if not row:
        raise HTTPException(status_code=404, detail="Version not found")
    return row


def _snapshot(version_id: int, refined_id: int) -> dict:
    row = first_row(
        supabase.table("finalized_submissions")
        .select("*")
        .eq("curriculum_version_id", version_id)
        .eq("refined_id", refined_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Version course not found")
    return row


def _course_summary(row: dict) -> dict:
    course = row.get("course_json") or {}
    return {
        "id": row["id"],
        "refined_id": row["refined_id"],
        "semester": course.get("semester") or "",
        "course_code": course.get("course_code") or "",
        "course_title": course.get("course_title") or "",
    }


@router.get("/versions")
def list_versions():
    try:
        rows = supabase.table("curriculum_versions").select("*").order("id", desc=True).execute().data
    except APIError as exc:
        raise database_http_exception(exc) from exc
    return {"versions": rows}


@router.post("/versions")
def create_version(payload: dict):
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Version name is required")

    try:
        rows = supabase.table("refined_submissions").select("*").execute().data
        rows = attach_submissions(rows)
        courses = [{"refined_id": row["id"], "course_json": build_course_preview(row)} for row in rows]
        version = (
            supabase.table("curriculum_versions")
            .insert(
                {
                    "name": name,
                    "program": str(payload.get("program") or (courses[0]["course_json"].get("program") if courses else "") or "").strip(),
                    "academic_year": str(payload.get("academic_year") or CURRICULUM_YEAR).strip(),
                    "status": str(payload.get("status") or "draft").strip(),
                }
            )
            .execute()
            .data[0]
        )
        if courses:
            records = [{**course, "curriculum_version_id": version["id"]} for course in courses]
            supabase.table("finalized_submissions").insert(records).execute()
    except APIError as exc:
        raise database_http_exception(exc) from exc
    return {"version": version, "courses": len(courses)}


@router.post("/versions/{version_id}/restore")
def restore_version(version_id: int):
    try:
        version = _version(version_id)
        rows = (
            supabase.table("finalized_submissions")
            .select("*")
            .eq("curriculum_version_id", version_id)
            .execute()
            .data
        )
        version_refined_ids = [row["refined_id"] for row in rows]
        current_rows = supabase.table("refined_submissions").select("*").execute().data
        current = {row["id"]: build_course_preview(row) for row in attach_submissions(current_rows)}
        current_status = {row["id"]: row.get("status") for row in current_rows}
        extra_ids = [row["id"] for row in current_rows if row["id"] not in version_refined_ids]
        history = []
        restored = 0
        for row in rows:
            refined_id = int(row["refined_id"])
            previous = current.get(refined_id)
            restored_course = row["course_json"]
            if not previous:
                continue
            if previous != restored_course:
                summary = diff_course(previous, restored_course)
                history.append(
                    {
                        "refined_id": refined_id,
                        "source": "version_restore",
                        "previous_json": previous,
                        "next_json": restored_course,
                        "json_patch": summary.pop("json_patch"),
                        "diff_summary": summary,
                        "change_reason": f"Restore version: {version['name']}",
                    }
                )
            if previous != restored_course or current_status.get(refined_id) != "refined":
                update_refined_fields(refined_id, {**restored_course, "status": "refined"})
                restored += 1
        if history:
            supabase.table("course_revision_history").insert(history).execute()
        if extra_ids:
            supabase.table("refined_submissions").update({"status": "archived"}).in_("id", extra_ids).execute()
    except APIError as exc:
        raise database_http_exception(exc) from exc
    return {"message": "Version restored", "version": version, "courses_restored": restored, "courses_archived": len(extra_ids)}


@router.get("/versions/{version_id}")
def get_version(version_id: int):
    try:
        version = _version(version_id)
        rows = (
            supabase.table("finalized_submissions")
            .select("*")
            .eq("curriculum_version_id", version_id)
            .execute()
            .data
        )
    except APIError as exc:
        raise database_http_exception(exc) from exc
    courses = [_course_summary(row) for row in rows]
    courses.sort(key=lambda course: (int(course.get("semester") or 0), str(course.get("course_code") or ""), str(course.get("course_title") or "")))
    return {"version": version, "courses": courses}


@router.get("/versions/{version_id}/courses/{refined_id}")
def get_version_course(version_id: int, refined_id: int):
    try:
        version = _version(version_id)
        snapshot = _snapshot(version_id, refined_id)
    except APIError as exc:
        raise database_http_exception(exc) from exc
    return {"version": version, "refined_id": refined_id, "fields": snapshot["course_json"]}


@router.get("/versions/{version_id}/courses/{refined_id}/preview")
def preview_version_course(version_id: int, refined_id: int):
    try:
        snapshot = _snapshot(version_id, refined_id)
    except APIError as exc:
        raise database_http_exception(exc) from exc
    version = _version(version_id)
    html = templates.get_template("jinja_sample.html").render(course=snapshot["course_json"], curriculum_year=version.get("academic_year") or CURRICULUM_YEAR, asset_root="/")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@router.get("/versions/{version_id}/preview")
def preview_version(version_id: int):
    try:
        version = _version(version_id)
        rows = (
            supabase.table("finalized_submissions")
            .select("*")
            .eq("curriculum_version_id", version_id)
            .order("refined_id")
            .execute()
            .data
        )
    except APIError as exc:
        raise database_http_exception(exc) from exc
    courses = sorted(
        (row["course_json"] for row in rows),
        key=lambda course: (int(course.get("semester") or 0), str(course.get("course_code") or ""), str(course.get("course_title") or "")),
    )
    html = templates.get_template("jinja_sample.html").render(courses=courses, semester="", curriculum_year=version.get("academic_year") or CURRICULUM_YEAR, asset_root="/")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})
