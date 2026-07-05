import sentry_sdk
from fastapi import APIRouter, BackgroundTasks, HTTPException
from postgrest.exceptions import APIError

from app.models.submission import CourseSubmission
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
    payload = data.model_dump()
    payload["status"] = "pending"
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
