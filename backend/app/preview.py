import json

from app.services.books import parse_books
from app.services.deterministic import compute_course_type, compute_hours, compute_program
from app.supabase import supabase


def _lines(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def _content(row: dict) -> dict:
    raw = row.get("refined_content") or {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        return json.loads(raw)
    return {}


def _text(*values) -> str:
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text and text != "-":
                return text
    return ""


def build_course_preview(row: dict) -> dict:
    content = _content(row)
    submission = row.get("_submission") or {}
    credit_category = str(submission.get("credit_category") or row.get("credit_category") or content.get("credits") or "")
    target_department = str(submission.get("target_department") or "")

    hours = {
        "lecture_hours": row.get("lecture_hours", content.get("lecture_hours", 0)),
        "tutorial_hours": row.get("tutorial_hours", content.get("tutorial_hours", 0)),
        "practical_hours": row.get("practical_hours", content.get("practical_hours", 0)),
        "self_study": row.get("self_study", content.get("self_study", 0)),
        "credits": row.get("credits", content.get("credits", 0)),
    }
    if credit_category and not any(hours.values()):
        hours = compute_hours(credit_category)

    program = row.get("program") or content.get("program") or ""
    if target_department and not program:
        program = compute_program(target_department)

    course_type = row.get("course_type") or content.get("course_type") or ""
    if credit_category and not course_type:
        course_type = compute_course_type(credit_category)

    practical_hours = int(hours["practical_hours"] or 0)
    status = str(row.get("status") or content.get("status") or "")

    objectives = _lines(row.get("objectives") or content.get("objectives"))[:4]
    course_outcomes = _lines(row.get("course_outcomes") or content.get("course_outcomes"))[:4]
    units = row.get("units") or content.get("units") or []
    lab_experiments = _lines(row.get("lab_experiments") or content.get("lab_experiments"))[:10] if practical_hours else []
    text_books = parse_books(row.get("text_books") or content.get("text_books")) or parse_books(submission.get("text_books"))
    reference_books = parse_books(row.get("reference_books") or content.get("reference_books")) or parse_books(submission.get("reference_books"))
    has_content = any([objectives, course_outcomes, units, lab_experiments, text_books, reference_books])
    return {
        "refined_id": row.get("id"),
        "course_code": str(row.get("course_code") or content.get("course_code") or ""),
        "course_title": str(row.get("course_title") or content.get("course_title") or ""),
        "program": str(program),
        "lecture_hours": str(hours["lecture_hours"]),
        "tutorial_hours": str(hours["tutorial_hours"]),
        "practical_hours": str(practical_hours),
        "self_study": str(hours["self_study"]),
        "credits": str(hours["credits"]),
        "semester": str(row.get("semester") or content.get("semester") or ""),
        "course_type": str(course_type),
        "is_elective": bool(row.get("is_elective") or content.get("is_elective") or False),
        "status": status,
        "render_detail": status != "summary_only" and has_content,
        "tools_languages": _text(row.get("tools_languages"), content.get("tools_languages"), submission.get("preferred_tools")),
        "desirable_knowledge": _text(row.get("desirable_knowledge"), content.get("desirable_knowledge")),
        "prelude": row.get("prelude") or content.get("prelude") or "",
        "objectives": objectives,
        "course_outcomes": course_outcomes,
        "units": units,
        "lab_experiments": lab_experiments,
        "text_books": text_books,
        "reference_books": reference_books,
    }


def build_specialization_context(academic_year: str = "") -> dict:
    """Load specialization tracks and their elective assignments for template rendering.

    academic_year is accepted for forward compatibility (multiple batches) but the
    current single-batch deployment returns every track. Filtering by an empty or
    mismatched year would hide all tracks, so we load them all and let the caller
    scope by semester inside the template.
    """
    specs = supabase.table("specialization_definitions").select("*").order("semester").order("letter").execute().data
    assignments = supabase.table("course_specialization_assignments").select("*").execute().data
    return {
        "specializations": specs,
        "specialization_assignments": assignments,
    }
