from fastapi import APIRouter, HTTPException
from postgrest.exceptions import APIError

from app import cache
from app.preview import build_course_preview
from app.services.curriculum import attach_submissions, invalidate_curriculum_cache
from app.services.errors import database_http_exception
from app.supabase import first_row, supabase

router = APIRouter()


@router.get("/courses")
def list_courses():
    cached = cache.get("courses_list")
    if cached is not None:
        return {"courses": cached}
    try:
        rows = supabase.table("refined_submissions").select("*").in_("status", ["refined"]).execute().data
        rows = attach_submissions(rows)
    except APIError as exc:
        raise database_http_exception(exc) from exc
    courses = [build_course_preview(row) | {"id": row["id"], "visible": row.get("visible", True)} for row in rows]
    courses.sort(key=lambda item: (int(item.get("semester") or 0), item.get("course_code") or "", item.get("course_title") or ""))
    cache.put("courses_list", courses, ttl=30)
    return {"courses": courses}


@router.patch("/courses/{refined_id}/visible")
def set_visibility(refined_id: int, body: dict):
    visible = body.get("visible")
    if not isinstance(visible, bool):
        raise HTTPException(status_code=400, detail="visible must be a boolean")
    try:
        row = first_row(supabase.table("refined_submissions").select("id").eq("id", refined_id).neq("status", "archived"))
        if not row:
            raise HTTPException(status_code=404, detail="Course not found")
        result = supabase.table("refined_submissions").update({"visible": visible}).eq("id", refined_id).execute()
    except APIError as exc:
        raise database_http_exception(exc) from exc
    cache.invalidate("courses_list")
    invalidate_curriculum_cache()
    return {"message": "Visibility updated", "course": result.data[0] if result.data else None}


@router.delete("/courses/{refined_id}")
def delete_course(refined_id: int):
    try:
        row = first_row(supabase.table("refined_submissions").select("id").eq("id", refined_id).neq("status", "archived"))
        if not row:
            raise HTTPException(status_code=404, detail="Course not found")
        result = supabase.table("refined_submissions").update({"status": "archived"}).eq("id", refined_id).execute()
    except APIError as exc:
        raise database_http_exception(exc) from exc
    cache.invalidate("courses_list")
    invalidate_curriculum_cache()
    return {"message": "Course removed", "course": result.data[0] if result.data else None}
