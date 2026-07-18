import logging
import os
import threading
import time as _time

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from weasyprint import HTML

from app import cache
from app.preview import build_course_preview, build_specialization_context
from app.rendering import FRONTEND_DIR, templates
from app.services.curriculum import attach_submissions, ordered_courses, selected_curriculum_year
from app.supabase import first_row, supabase

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/preview/semester/{sem}/courses")
def list_courses(sem: int):
    result = supabase.table("refined_submissions").select("id,status").in_("status", ["refined"]).eq("visible", True).eq("semester", sem).order("id").execute()
    return {"course_ids": [row["id"] for row in result.data]}


@router.get("/preview/pending-courses")
def list_pending_courses():
    result = supabase.table("refined_submissions").select("id,course_code,course_title").eq("status", "draft").eq("visible", True).order("id").execute()
    return {"courses": [{"id": row["id"], "course_code": row.get("course_code") or "", "course_title": row.get("course_title") or ""} for row in result.data]}


@router.get("/preview/courses")
def list_all_courses():
    result = supabase.table("refined_submissions").select("id,semester,course_code").in_("status", ["refined"]).eq("visible", True).execute()
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
    cy = selected_curriculum_year(curriculum_year)
    cache_key = f"full_html:{cy}"
    cached = cache.get(cache_key)
    if cached is not None:
        return HTMLResponse(cached, headers={"Cache-Control": "public, max-age=30, s-maxage=300, stale-while-revalidate=600"})
    result = supabase.table("refined_submissions").select("*").in_("status", ["refined"]).eq("visible", True).execute()
    courses = ordered_courses(result.data)
    html = templates.get_template("jinja_sample.html").render(
        courses=courses,
        semester="",
        curriculum_year=cy,
        asset_root="/",
        show_summaries=True,
        **build_specialization_context(cy),
    )
    cache.put(cache_key, html, ttl=120)
    return HTMLResponse(html, headers={"Cache-Control": "public, max-age=30, s-maxage=300, stale-while-revalidate=600"})


@router.get("/preview/pdf")
def download_all_pdf(download: bool = Query(False), curriculum_year: str | None = Query(None)):
    cy = selected_curriculum_year(curriculum_year)
    cache_key = f"full_pdf:{cy}"
    cached = cache.get(cache_key)
    if cached is not None:
        return pdf_response(cached, "curriculum-preview.pdf", download)
    result = supabase.table("refined_submissions").select("*").in_("status", ["refined"]).eq("visible", True).execute()
    courses = ordered_courses(result.data)
    html = templates.get_template("jinja_sample.html").render(
        courses=courses,
        semester="",
        curriculum_year=cy,
        asset_root="",
        show_summaries=True,
        **build_specialization_context(cy),
    )
    pdf = HTML(string=html, base_url=str(FRONTEND_DIR)).write_pdf()
    cache.put(cache_key, pdf, ttl=120)
    return pdf_response(pdf, "curriculum-preview.pdf", download)


@router.get("/preview/semester/{sem}/pdf")
def download_pdf(sem: int, download: bool = Query(False), curriculum_year: str | None = Query(None)):
    cy = selected_curriculum_year(curriculum_year)
    cache_key = f"sem_pdf:{sem}:{cy}"
    cached = cache.get(cache_key)
    if cached is not None:
        return pdf_response(cached, f"semester-{sem}.pdf", download)
    result = supabase.table("refined_submissions").select("*").in_("status", ["refined"]).eq("visible", True).eq("semester", sem).order("id").execute()
    courses = ordered_courses(result.data)
    html = templates.get_template("jinja_sample.html").render(
        courses=courses,
        semester=sem,
        curriculum_year=cy,
        asset_root="",
        show_summaries=True,
        **build_specialization_context(cy),
    )
    pdf = HTML(string=html, base_url=str(FRONTEND_DIR)).write_pdf()
    cache.put(cache_key, pdf, ttl=120)
    return pdf_response(pdf, f"semester-{sem}.pdf", download)


def pdf_response(pdf: bytes, filename: str, download: bool) -> Response:
    disposition = "attachment" if download else "inline"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "public, max-age=30, s-maxage=300, stale-while-revalidate=600",
        },
    )


def _generate_pdf(cy: str) -> bytes | None:
    try:
        result = supabase.table("refined_submissions").select("*").in_("status", ["refined"]).eq("visible", True).execute()
        courses = ordered_courses(result.data)
        html = templates.get_template("jinja_sample.html").render(
            courses=courses,
            semester="",
            curriculum_year=cy,
            asset_root="",
            show_summaries=True,
            **build_specialization_context(cy),
        )
        return HTML(string=html, base_url=str(FRONTEND_DIR)).write_pdf()
    except Exception:
        logger.exception("PDF preload failed for year=%s", cy)
        return None


def preload_pdfs() -> None:
    """Generate and cache PDFs for all configured curriculum years on startup."""
    years_raw = os.getenv("CURRICULUM_YEAR", "").strip()
    years = [y.strip() for y in years_raw.split(",") if y.strip()]
    if not years:
        return

    def _worker():
        for cy in years:
            t0 = _time.monotonic()
            pdf = _generate_pdf(cy)
            if pdf:
                cache.put(f"full_pdf:{cy}", pdf, ttl=3600)
                elapsed = (_time.monotonic() - t0) * 1000
                logger.info("PDF preload complete for year=%s in %dms (%d bytes)", cy, elapsed, len(pdf))
            else:
                logger.warning("PDF preload skipped for year=%s", cy)

    thread = threading.Thread(target=_worker, daemon=True, name="pdf-preload")
    thread.start()
