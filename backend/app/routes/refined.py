from fastapi import APIRouter, HTTPException

from app.preview import build_course_preview
from app.services.curriculum import attach_submissions, update_refined_fields
from app.supabase import first_row, supabase

router = APIRouter()


@router.get("/refined/{refined_id}")
def get_refined(refined_id: int):
    row = first_row(supabase.table("refined_submissions").select("*").eq("id", refined_id))
    if not row:
        raise HTTPException(status_code=404, detail="Refined submission not found")
    row = attach_submissions([row])[0]
    return {"id": refined_id, "fields": build_course_preview(row)}


@router.patch("/refined/{refined_id}")
def update_refined(refined_id: int, payload: dict):
    fields = payload.get("fields")
    if not isinstance(fields, dict):
        raise HTTPException(status_code=400, detail="fields is required")
    try:
        return {"message": "Updated", "data": update_refined_fields(refined_id, fields)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
