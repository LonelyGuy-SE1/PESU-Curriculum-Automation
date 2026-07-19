import sentry_sdk
from fastapi import APIRouter, BackgroundTasks, HTTPException
from postgrest.exceptions import APIError

from app.models.submission import CourseSubmission, parse_course_code
from app.services.errors import database_http_exception
from app.services.refinement import refine
from app.supabase import supabase

router = APIRouter()


def refine_later(submission_id: int) -> None:
    try:
        refine(submission_id)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        supabase.table("submissions").update({"status": "refine_failed"}).eq("id", submission_id).execute()


@router.post("/submissions")
def receive(data: CourseSubmission, background_tasks: BackgroundTasks):
    parsed = parse_course_code(data.course_code)
    payload = data.model_dump()
    user_credit = (payload.get("credit_category") or "").strip()
    if user_credit in ("0", "2", "4", "5"):
        credit_cat = user_credit
    else:
        credit_cat = parsed.credit_category
    raw = data.raw_course_content or ""
    if "Course Code" not in raw:
        raw = f"Course Code: {data.course_code}\n{raw}"
    payload.pop("course_code", None)
    payload["raw_course_content"] = raw
    payload.update({
        "offering_department": parsed.offering_dept,
        "target_department": parsed.target_dept,
        "semester": int(parsed.semester),
        "credit_category": credit_cat,
        "status": "pending",
    })
    try:
        result = supabase.table("submissions").insert(payload).execute()
    except APIError as exc:
        raise database_http_exception(exc) from exc
    submission = result.data[0]
    background_tasks.add_task(refine_later, submission["id"])
    return {"message": "Submission Received!", "submission": submission}


@router.post("/submissions/{id}/refine")
def refine_submission(id: int):
    try:
        return {"message": "Refined", "data": refine(id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except APIError as exc:
        raise database_http_exception(exc) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"Refinement failed: {exc}") from exc
