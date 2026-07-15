from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from weasyprint import HTML

from app.preview import build_course_preview, build_specialization_context
from app.rendering import FRONTEND_DIR, templates
from app.services.curriculum import attach_submissions, ordered_courses, selected_curriculum_year
from app.supabase import first_row, supabase

router = APIRouter()


@router.get("/preview/semester/{sem}/courses")
def list_courses(sem: int):
    result = supabase.table("refined_submissions").select("id").neq("status", "archived").eq("visible", True).eq("semester", sem).order("id").execute()
    return {"course_ids": [row["id"] for row in result.data]}


@router.get("/preview/courses")
def list_all_courses():
    result = supabase.table("refined_submissions").select("id,semester,course_code").neq("status", "archived").eq("visible", True).execute()
    rows = sorted(result.data, key=lambda row: (int(row.get("semester") or 0), str(row.get("course_code") or ""), int(row.get("id") or 0)))
    return {"course_ids": [row["id"] for row in rows]}


@router.get("/preview/course/{refined_id}")
def preview_course(refined_id: int, curriculum_year: str | None = Query(None)):
    row = first_row(supabase.table("refined_submissions").select("*").eq("id", refined_id))
    if not row:
        raise HTTPException(status_code=404, detail="Refined submission not found")
    row = attach_submissions([row])[0]
    html = templates.get_template("jinja_sample.html").render(
        course=build_course_preview(row),
        curriculum_year=selected_curriculum_year(curriculum_year),
        asset_root="/",
    )
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@router.get("/preview/html")
def preview_all_html(curriculum_year: str | None = Query(None)):
    result = supabase.table("refined_submissions").select("*").neq("status", "archived").eq("visible", True).execute()
    courses = ordered_courses(result.data)
    html = templates.get_template("jinja_sample.html").render(
        courses=courses,
        semester="",
        curriculum_year=selected_curriculum_year(curriculum_year),
        asset_root="/",
        show_summaries=True,
        **build_specialization_context(selected_curriculum_year(curriculum_year)),
    )
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@router.get("/preview/pdf")
def download_all_pdf(download: bool = Query(False), curriculum_year: str | None = Query(None)):
    result = supabase.table("refined_submissions").select("*").neq("status", "archived").eq("visible", True).execute()
    courses = ordered_courses(result.data)
    html = templates.get_template("jinja_sample.html").render(
        courses=courses,
        semester="",
        curriculum_year=selected_curriculum_year(curriculum_year),
        asset_root="",
        show_summaries=True,
        **build_specialization_context(selected_curriculum_year(curriculum_year)),
    )
    pdf = HTML(string=html, base_url=str(FRONTEND_DIR)).write_pdf()
    return pdf_response(pdf, "curriculum-preview.pdf", download)


@router.get("/preview/semester/{sem}/pdf")
def download_pdf(sem: int, download: bool = Query(False), curriculum_year: str | None = Query(None)):
    result = supabase.table("refined_submissions").select("*").neq("status", "archived").eq("visible", True).eq("semester", sem).order("id").execute()
    courses = ordered_courses(result.data)
    html = templates.get_template("jinja_sample.html").render(
        courses=courses,
        semester=sem,
        curriculum_year=selected_curriculum_year(curriculum_year),
        asset_root="",
        show_summaries=True,
        **build_specialization_context(selected_curriculum_year(curriculum_year)),
    )
    pdf = HTML(string=html, base_url=str(FRONTEND_DIR)).write_pdf()
    return pdf_response(pdf, f"semester-{sem}.pdf", download)


def pdf_response(pdf: bytes, filename: str, download: bool) -> Response:
    disposition = "attachment" if download else "inline"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"', "Cache-Control": "no-store"},
    )
