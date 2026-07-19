from os import environ

from app import cache
from app.preview import build_course_preview
from app.services.diffing import diff_course, merge_fields, validate_draft
from app.supabase import first_row, supabase

DEFAULT_CURRICULUM_YEAR = environ.get("CURRICULUM_YEAR", "").strip()


def invalidate_curriculum_cache():
    """Invalidate all cached curriculum PDF/HTML after data changes."""
    cache.invalidate("full_pdf:")
    cache.invalidate("full_html:")
    cache.invalidate("sem_pdf:")
    cache.invalidate("course:")
    cache.invalidate("course_html:")
    cache.invalidate("sem_courses:")
    cache.invalidate("pending_courses")
    cache.invalidate("all_course_ids")
    cache.invalidate("ver_preview:")
SOURCE_ORDER = {
    "UE25CS151A": 1,
    "UE25CS151B": 1,
    "UE24CS251A": 1,
    "UE24CS252A": 2,
    "UE24MA242A": 3,
    "UE24CS241A": 4,
    "UE24CS243A": 5,
    "UZ24UZ221A": 6,
    "UE25MA201A*": 7,
    "UE24CS251B": 1,
    "UE24CS252B": 2,
    "UE24CS241B": 3,
    "UE24CS242B": 4,
    "UE24MA241B": 5,
    "UZ24UZ221B": 6,
    "UE25MA201B*": 7,
    "UE23CS351A": 1,
    "UE23CS352A": 2,
    "UE23CS341A": 3,
    "UE23CS342AAX": 4,
    "UE23CS343ABX": 5,
    "UE23CS320A": 6,
    "UE23CS351B": 1,
    "UE23CS352B": 2,
    "UE23CS341B": 3,
    "UE23CS342BAX": 4,
    "UE23CS343BBX": 5,
    "UE23CS320B": 6,
    "UE22CS441A": 1,
    "UZ22UZ422A": 2,
    "UE22AM421AXX": 3,
    "UE22CS421B": 1,
    "UE22CS461XB": 2,
}

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


def attach_submissions(rows: list[dict]) -> list[dict]:
    ids = [row["submission_id"] for row in rows if row.get("submission_id")]
    if not ids:
        return rows
    cache_key = f"attach:{','.join(str(i) for i in sorted(ids))}"
    cached = cache.get(cache_key)
    if cached is not None:
        for row in rows:
            row["_submission"] = cached.get(row.get("submission_id"), {})
        return rows
    submissions = supabase.table("submissions").select("*").in_("id", ids).execute().data
    by_id = {row["id"]: row for row in submissions}
    cache.put(cache_key, by_id, ttl=300)
    for row in rows:
        row["_submission"] = by_id.get(row.get("submission_id"), {})
    return rows


def ordered_courses(rows: list[dict]) -> list[dict]:
    rows = attach_submissions(rows)
    rows.sort(key=course_sort_key)
    return [build_course_preview(row) for row in rows]


def course_credits(row: dict) -> int:
    value = row.get("credits")
    if value not in (None, ""):
        return int(value)
    category = str((row.get("_submission") or {}).get("credit_category") or "").strip()
    if category.isdigit():
        return int(category)
    return 0


def course_sort_key(row: dict) -> tuple[int, int, int, int]:
    semester = int(row.get("semester") or 0)
    code = str(row.get("course_code") or "").replace(" ", "").upper()
    order = SOURCE_ORDER.get(code)
    if order is None and semester == 5:
        order = elective_order(code, "AA", "AB")
    if order is None and semester == 6:
        order = elective_order(code, "BA", "BB")
    return semester, -course_credits(row), order or 900, int(row.get("id") or 0)


def elective_order(code: str, first_group: str, second_group: str) -> int | None:
    for offset, group in ((100, first_group), (200, second_group)):
        if group in code:
            suffix = code.rsplit(group, 1)[-1].rstrip("X")
            return offset + int(suffix) if suffix.isdigit() else offset
    return None


def create_version_snapshot(name: str) -> dict:
    rows = supabase.table("refined_submissions").select("*").in_("status", ["refined"]).execute().data
    rows = attach_submissions(rows)
    courses = [{"refined_id": row["id"], "course_json": build_course_preview(row)} for row in rows]
    program = courses[0]["course_json"].get("program") if courses else ""
    version = (
        supabase.table("curriculum_versions")
        .insert({"name": name, "program": program, "academic_year": selected_curriculum_year(), "status": "draft"})
        .execute().data[0]
    )
    if courses:
        records = [{**course, "curriculum_version_id": version["id"]} for course in courses]
        supabase.table("finalized_submissions").insert(records).execute()
    return version


def selected_curriculum_year(override: str | None = None) -> str:
    if override and override.strip():
        return override.strip()
    return DEFAULT_CURRICULUM_YEAR


def refined_course(refined_id: int) -> dict:
    cache_key = f"course:{refined_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    row = first_row(supabase.table("refined_submissions").select("*").eq("id", refined_id))
    if not row:
        raise LookupError("Refined submission not found")
    result = build_course_preview(attach_submissions([row])[0])
    cache.put(cache_key, result, ttl=300)
    return result


def update_refined_fields(refined_id: int, fields: dict) -> dict | None:
    update = {key: fields[key] for key in REFINED_FIELDS if key in fields}
    for key in ("semester", "lecture_hours", "tutorial_hours", "practical_hours", "self_study", "credits"):
        if key in update:
            try:
                update[key] = int(update[key] or 0)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid value for {key}: {update[key]!r}. Must be a number.") from exc
    row = first_row(supabase.table("refined_submissions").select("status").eq("id", refined_id))
    if row and row.get("status") == "draft":
        update["status"] = "refined"
    result = supabase.table("refined_submissions").update(update).eq("id", refined_id).execute()
    invalidate_curriculum_cache()
    return result.data[0] if result.data else None


def draft_record(refined_id: int, fields: dict, reason: str = "", document_draft_id: int | None = None) -> dict:
    base = refined_course(refined_id)
    proposed = merge_fields(base, fields)
    summary = diff_course(base, proposed)
    issues = validate_draft(base, proposed)
    summary["validation_issues"] = issues
    return {
        "refined_id": refined_id,
        "document_draft_id": document_draft_id,
        "base_refined_json": base,
        "proposed_json": proposed,
        "json_patch": summary.pop("json_patch"),
        "diff_summary": summary,
        "change_reason": reason.strip(),
        "status": "blocked" if issues else "proposed",
    }


def load_agent_draft(draft_id: int) -> dict:
    draft = first_row(supabase.table("agent_drafts").select("*").eq("id", draft_id))
    if not draft:
        raise LookupError("Agent draft not found")
    return draft


def load_document_draft(document_draft_id: int) -> dict:
    document = first_row(supabase.table("agent_document_drafts").select("*").eq("id", document_draft_id))
    if not document:
        raise LookupError("Document draft not found")
    drafts = supabase.table("agent_drafts").select("*").eq("document_draft_id", document_draft_id).order("id").execute().data
    return {"document_draft": document, "drafts": drafts}
