"""Guarded AI categorization for newly refined elective courses."""

import logging

from app.services.openrouter import call as llm
from app.supabase import first_row, supabase

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.80
ELECTIVE_MARKERS = ("AA", "AB", "BA", "BB")
SYSTEM_PROMPT = """You categorize PES University elective courses into existing specialization tracks.
Return only valid JSON in this exact shape:
{"confidence": 0.0, "assignments": [{"specialization_id": 1, "confidence": 0.0, "reasoning": "Short evidence-based reason."}]}
Use only IDs supplied in the prompt. Never invent a track or ID. Assign only clear matches.
For no clear match, return an empty assignments list and confidence below 0.80.
"""


def is_elective_course(course: dict) -> bool:
    """Mirror the legacy elective-code grouping rule for semesters 5 and 6."""
    code = str(course.get("course_code") or "").replace(" ", "").upper()
    return int(course.get("semester") or 0) in (5, 6) and any(
        marker in code for marker in ELECTIVE_MARKERS
    )


def _course_content(course: dict) -> str:
    """Extract a flat text representation of course content for the LLM prompt."""
    units = course.get("units") or []
    unit_text = []
    if isinstance(units, list):
        for unit in units:
            if isinstance(unit, dict):
                unit_text.append(
                    f"{unit.get('title', '')}: {unit.get('content', '')}".strip()
                )
            else:
                unit_text.append(str(unit))
    parts = [
        course.get("course_title"),
        course.get("prelude"),
        course.get("objectives"),
        course.get("course_outcomes"),
        *unit_text,
        course.get("tools_languages"),
    ]
    return "\n".join(str(p) for p in parts if p).strip()[:18000]


def _confirmation(reason: str, **extra) -> dict:
    return {"assigned": False, "needs_human_confirmation": True, "reason": reason, **extra}


def _fetch_tracks(semester: int) -> list[dict]:
    """Return specialization definitions for the given semester."""
    return (
        supabase.table("specialization_definitions")
        .select("id,semester,letter,name,key,academic_year")
        .eq("semester", semester)
        .order("letter")
        .execute()
        .data
    )


def _validate_assignments(assignments: list, valid_ids: set[int]) -> dict | None:
    """Validate each assignment entry; returns an error confirmation or None on success."""
    seen: set[int] = set()
    for assignment in assignments:
        try:
            spec_id = int(assignment["specialization_id"])
            conf = float(assignment["confidence"])
            reasoning = str(assignment["reasoning"]).strip()
        except (KeyError, TypeError, ValueError):
            return _confirmation("invalid_model_assignment")
        if spec_id not in valid_ids:
            return _confirmation(
                "unknown_specialization_id", specialization_id=spec_id
            )
        if conf < MIN_CONFIDENCE or not reasoning:
            return _confirmation(
                "low_assignment_confidence", specialization_id=spec_id
            )
        if spec_id not in seen:
            seen.add(spec_id)
    return None


def _persist_assignments(refined_id: int, accepted: list[dict]) -> int:
    """Insert accepted assignments into the DB; returns the number created."""
    created = 0
    for assignment in accepted:
        spec_id = assignment["specialization_id"]
        exists = (
            supabase.table("course_specialization_assignments")
            .select("id")
            .eq("refined_id", refined_id)
            .eq("specialization_id", spec_id)
            .execute()
            .data
        )
        if not exists:
            supabase.table("course_specialization_assignments").insert(
                {"refined_id": refined_id, "specialization_id": spec_id}
            ).execute()
            created += 1
    return created


def _parse_llm_response(result) -> tuple[float, list[dict]] | None:
    """Parse and validate the LLM response; returns (confidence, assignments) or None."""
    if not isinstance(result, dict):
        return None
    try:
        confidence = float(result.get("confidence"))
    except (TypeError, ValueError):
        return None
    assignments = result.get("assignments")
    if not isinstance(assignments, list) or not assignments:
        return None
    return confidence, assignments


def categorize_refined_elective(refined_id: int) -> dict:
    """Assign only existing specialization tracks with validated high-confidence output."""
    course = first_row(
        supabase.table("refined_submissions").select("*").eq("id", refined_id)
    )
    if not course:
        raise LookupError("Refined submission not found")
    if not course.get("is_elective") and not is_elective_course(course):
        return {
            "assigned": False,
            "needs_human_confirmation": False,
            "reason": "not_an_elective",
        }
    if not course.get("is_elective"):
        supabase.table("refined_submissions").update({"is_elective": True}).eq(
            "id", refined_id
        ).execute()

    tracks = _fetch_tracks(int(course["semester"]))
    if not tracks:
        return _confirmation("no_specializations_for_semester", refined_id=refined_id)

    try:
        result = llm(
            SYSTEM_PROMPT,
            f"""Course ID: {refined_id}
Course code: {course.get("course_code") or ""}
Course content:
{_course_content(course)}
Available specialization tracks: {tracks}""",
        )
    except Exception:
        logger.exception(
            "Elective categorization model call failed for refined_id=%s", refined_id
        )
        return _confirmation("model_error", refined_id=refined_id)

    parsed = _parse_llm_response(result)
    if parsed is None:
        return _confirmation("invalid_model_response", refined_id=refined_id)

    confidence, assignments = parsed
    if confidence < MIN_CONFIDENCE:
        return _confirmation(
            "low_confidence_or_no_match", refined_id=refined_id, confidence=confidence
        )

    valid_ids = {int(track["id"]) for track in tracks}
    validation_error = _validate_assignments(assignments, valid_ids)
    if validation_error:
        validation_error["refined_id"] = refined_id
        return validation_error

    seen: set[int] = set()
    accepted: list[dict] = []
    for assignment in assignments:
        spec_id = int(assignment["specialization_id"])
        if spec_id not in seen:
            seen.add(spec_id)
            accepted.append(
                {
                    "specialization_id": spec_id,
                    "confidence": float(assignment["confidence"]),
                    "reasoning": str(assignment["reasoning"]).strip(),
                }
            )

    created = _persist_assignments(refined_id, accepted)
    logger.info(
        "Elective categorization refined_id=%s assignments=%s", refined_id, accepted
    )
    return {
        "assigned": True,
        "needs_human_confirmation": False,
        "refined_id": refined_id,
        "assignments_created": created,
        "assignments": accepted,
    }
