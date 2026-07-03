import re
from pathlib import Path
from typing import Literal

import sentry_sdk
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape
from pydantic import BaseModel, Field, field_validator
from weasyprint import HTML

from app.preview import build_course_preview
from app.services.refinement import refine
from app.supabase import supabase

router = APIRouter()
APP_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = APP_DIR.parent.parent / "frontend"
templates = Environment(loader=FileSystemLoader(APP_DIR / "templates"), autoescape=select_autoescape(["html", "xml"]))
URL_RE = re.compile(r"https?://[^\s<>()]+")

REFINED_FIELDS = {
    "semester",
    "course_code",
    "course_title",
    "program",
    "lecture_hours",
    "tutorial_hours",
    "practical_hours",
    "self_study",
    "credits",
    "course_type",
    "tools_languages",
    "desirable_knowledge",
    "prelude",
    "objectives",
    "course_outcomes",
    "units",
    "lab_experiments",
    "text_books",
    "reference_books",
    "status",
}


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


def attach_submissions(rows: list[dict]) -> list[dict]:
    ids = [row["submission_id"] for row in rows if row.get("submission_id")]
    if not ids:
        return rows
    submissions = supabase.table("submissions").select("*").in_("id", ids).execute().data
    by_id = {row["id"]: row for row in submissions}
    for row in rows:
        row["_submission"] = by_id.get(row.get("submission_id"), {})
    return rows


def ordered_courses(rows: list[dict]) -> list[dict]:
    rows = attach_submissions(rows)
    rows.sort(key=lambda row: (int(row.get("semester") or 0), str(row.get("course_code") or ""), int(row.get("id") or 0)))
    return [build_course_preview(row) for row in rows]


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
    update = {key: fields[key] for key in REFINED_FIELDS if key in fields}
    for key in ("semester", "lecture_hours", "tutorial_hours", "practical_hours", "self_study", "credits"):
        if key in update:
            update[key] = int(update[key] or 0)
    result = supabase.table("refined_submissions").update(update).eq("id", refined_id).execute()
    return {"message": "Updated", "data": result.data[0] if result.data else None}
