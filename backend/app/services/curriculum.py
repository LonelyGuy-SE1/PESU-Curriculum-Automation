from app.preview import build_course_preview
from app.services.diffing import diff_course, merge_fields, validate_draft
from app.supabase import first_row, supabase

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
    submissions = supabase.table("submissions").select("*").in_("id", ids).execute().data
    by_id = {row["id"]: row for row in submissions}
    for row in rows:
        row["_submission"] = by_id.get(row.get("submission_id"), {})
    return rows


def ordered_courses(rows: list[dict]) -> list[dict]:
    rows = attach_submissions(rows)
    rows.sort(key=lambda row: (int(row.get("semester") or 0), str(row.get("course_code") or ""), int(row.get("id") or 0)))
    return [build_course_preview(row) for row in rows]


def refined_course(refined_id: int) -> dict:
    row = first_row(supabase.table("refined_submissions").select("*").eq("id", refined_id))
    if not row:
        raise LookupError("Refined submission not found")
    return build_course_preview(attach_submissions([row])[0])


def update_refined_fields(refined_id: int, fields: dict) -> dict | None:
    update = {key: fields[key] for key in REFINED_FIELDS if key in fields}
    for key in ("semester", "lecture_hours", "tutorial_hours", "practical_hours", "self_study", "credits"):
        if key in update:
            update[key] = int(update[key] or 0)
    result = supabase.table("refined_submissions").update(update).eq("id", refined_id).execute()
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
