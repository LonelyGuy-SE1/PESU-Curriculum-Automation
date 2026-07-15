from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from postgrest.exceptions import APIError

from app.preview import build_course_preview, build_specialization_context
from app.rendering import templates
from app.services.curriculum import attach_submissions, DEFAULT_CURRICULUM_YEAR, selected_curriculum_year, update_refined_fields
from app.services.diffing import diff_course
from app.services.errors import database_http_exception
from app.supabase import first_row, supabase

router = APIRouter()


def _version(version_id: int) -> dict:
    row = first_row(supabase.table("curriculum_versions").select("*").eq("id", version_id))
    if not row:
        raise HTTPException(status_code=404, detail="Version not found")
    return row


def _snapshot(version_id: int, refined_id: int) -> dict:
    row = first_row(
        supabase.table("finalized_submissions")
        .select("*")
        .eq("curriculum_version_id", version_id)
        .eq("refined_id", refined_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Version course not found")
    return row


def _course_summary(row: dict) -> dict:
    course = row.get("course_json") or {}
    return {
        "id": row["id"],
        "refined_id": row["refined_id"],
        "semester": course.get("semester") or "",
        "course_code": course.get("course_code") or "",
        "course_title": course.get("course_title") or "",
    }


@router.get("/versions")
def list_versions():
    try:
        rows = supabase.table("curriculum_versions").select("*").order("id", desc=True).execute().data
    except APIError as exc:
        raise database_http_exception(exc) from exc
    return {"versions": rows}


@router.patch("/versions/{version_id}")
def update_version(version_id: int, payload: dict):
    _version(version_id)
    updates = {}
    if "name" in payload:
        updates["name"] = str(payload["name"]).strip()
    if "academic_year" in payload:
        updates["academic_year"] = str(payload["academic_year"]).strip()
    if "status" in payload:
        updates["status"] = str(payload["status"]).strip()
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        row = supabase.table("curriculum_versions").update(updates).eq("id", version_id).execute().data[0]
    except APIError as exc:
        raise database_http_exception(exc) from exc
    return {"version": row}


@router.post("/versions")
def create_version(payload: dict):
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Version name is required")

    try:
        rows = supabase.table("refined_submissions").select("*").execute().data
        rows = attach_submissions(rows)
        courses = [{"refined_id": row["id"], "course_json": build_course_preview(row)} for row in rows]
        version = (
            supabase.table("curriculum_versions")
            .insert(
                {
                    "name": name,
                    "program": str(payload.get("program") or (courses[0]["course_json"].get("program") if courses else "") or "").strip(),
                    "academic_year": str(payload.get("academic_year") or DEFAULT_CURRICULUM_YEAR).strip(),
                    "status": str(payload.get("status") or "draft").strip(),
                }
            )
            .execute()
            .data[0]
        )
        if courses:
            records = [{**course, "curriculum_version_id": version["id"]} for course in courses]
            supabase.table("finalized_submissions").insert(records).execute()
    except APIError as exc:
        raise database_http_exception(exc) from exc
    return {"version": version, "courses": len(courses)}


@router.post("/versions/{version_id}/restore")
def restore_version(version_id: int):
    try:
        version = _version(version_id)
        rows = (
            supabase.table("finalized_submissions")
            .select("*")
            .eq("curriculum_version_id", version_id)
            .execute()
            .data
        )
        version_refined_ids = [row["refined_id"] for row in rows]
        current_rows = supabase.table("refined_submissions").select("*").execute().data
        current = {row["id"]: build_course_preview(row) for row in attach_submissions(current_rows)}
        current_status = {row["id"]: row.get("status") for row in current_rows}
        extra_ids = [row["id"] for row in current_rows if row["id"] not in version_refined_ids]
        history = []
        restored = 0
        for row in rows:
            refined_id = int(row["refined_id"])
            previous = current.get(refined_id)
            restored_course = row["course_json"]
            if not previous:
                continue
            if previous != restored_course:
                summary = diff_course(previous, restored_course)
                history.append(
                    {
                        "refined_id": refined_id,
                        "source": "version_restore",
                        "previous_json": previous,
                        "next_json": restored_course,
                        "json_patch": summary.pop("json_patch"),
                        "diff_summary": summary,
                        "change_reason": f"Restore version: {version['name']}",
                    }
                )
            if previous != restored_course or current_status.get(refined_id) != "refined":
                update_refined_fields(refined_id, {**restored_course, "status": "refined"})
                restored += 1
        if history:
            supabase.table("course_revision_history").insert(history).execute()
        if extra_ids:
            supabase.table("refined_submissions").update({"status": "archived"}).in_("id", extra_ids).execute()
        supabase.table("agent_drafts").update({"status": "proposed"}).eq("status", "applied").execute()
        supabase.table("agent_document_drafts").update({"status": "proposed"}).eq("status", "applied").execute()
    except APIError as exc:
        raise database_http_exception(exc) from exc
    return {"message": "Version restored", "version": version, "courses_restored": restored, "courses_archived": len(extra_ids)}


@router.get("/versions/{version_id}")
def get_version(version_id: int):
    try:
        version = _version(version_id)
        rows = (
            supabase.table("finalized_submissions")
            .select("*")
            .eq("curriculum_version_id", version_id)
            .execute()
            .data
        )
    except APIError as exc:
        raise database_http_exception(exc) from exc
    courses = [_course_summary(row) for row in rows]
    courses.sort(key=lambda course: (int(course.get("semester") or 0), str(course.get("course_code") or ""), str(course.get("course_title") or "")))
    return {"version": version, "courses": courses}


@router.get("/versions/{version_id}/courses/{refined_id}")
def get_version_course(version_id: int, refined_id: int):
    try:
        version = _version(version_id)
        snapshot = _snapshot(version_id, refined_id)
    except APIError as exc:
        raise database_http_exception(exc) from exc
    return {"version": version, "refined_id": refined_id, "fields": snapshot["course_json"]}


@router.get("/versions/{version_id}/courses/{refined_id}/preview")
def preview_version_course(version_id: int, refined_id: int, curriculum_year: str | None = Query(None)):
    try:
        snapshot = _snapshot(version_id, refined_id)
    except APIError as exc:
        raise database_http_exception(exc) from exc
    version = _version(version_id)
    html = templates.get_template("jinja_sample.html").render(course=snapshot["course_json"], curriculum_year=selected_curriculum_year(curriculum_year), asset_root="/")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@router.get("/versions/{version_id}/preview")
def preview_version(version_id: int, diff: bool = Query(False), curriculum_year: str | None = Query(None)):
    try:
        version = _version(version_id)
        rows = (
            supabase.table("finalized_submissions")
            .select("*")
            .eq("curriculum_version_id", version_id)
            .order("refined_id")
            .execute()
            .data
        )
    except APIError as exc:
        raise database_http_exception(exc) from exc

    version_courses = sorted(
        ({"refined_id": row["refined_id"], **row["course_json"]} for row in rows),
        key=lambda course: (int(course.get("semester") or 0), str(course.get("course_code") or ""), str(course.get("course_title") or "")),
    )

    if not diff:
        html = templates.get_template("jinja_sample.html").render(
            courses=version_courses,
            semester="",
            curriculum_year=selected_curriculum_year(curriculum_year),
            asset_root="/",
            show_summaries=True,
            **build_specialization_context(selected_curriculum_year(curriculum_year)),
        )
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    # Diff mode: compare version against current refined submissions
    current_rows = supabase.table("refined_submissions").select("*").neq("status", "archived").execute().data
    current_rows = attach_submissions(current_rows)
    current = {row["id"]: build_course_preview(row) for row in current_rows}

    course_diffs = []
    for v_course in version_courses:
        refined_id = v_course.get("refined_id")
        current_course = current.get(refined_id)
        if current_course:
            base = dict(current_course)
            proposed = dict(v_course)
            course_diff = _build_course_diff(proposed, base)
            if any(v is not None for v in course_diff.values()):
                course_diffs.append({"base": base, "proposed": proposed, "course_diff": course_diff})

    html = templates.get_template("jinja_diff.html").render(
        course_diffs=course_diffs,
        curriculum_year=selected_curriculum_year(curriculum_year),
        asset_root="/",
    )
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


def _diff_text_field(old: str, new: str) -> dict | None:
    if old == new:
        return None
    return {"kind": "text", "old": old or "", "new": new or ""}


def _diff_list_field(old: list, new: list) -> dict | None:
    if old == new:
        return None
    old_set = set(old)
    new_set = set(new)
    return {
        "kind": "list",
        "removed": sorted(old_set - new_set),
        "added": sorted(new_set - old_set),
        "unchanged": sorted(old_set & new_set),
    }


def _diff_units_field(old_units: list, new_units: list) -> dict | None:
    if old_units == new_units:
        return None
    old_by_title = {u.get("title", ""): u for u in old_units if isinstance(u, dict)}
    new_by_title = {u.get("title", ""): u for u in new_units if isinstance(u, dict)}
    all_titles = sorted(set(old_by_title.keys()) | set(new_by_title.keys()))

    units_diff = []
    for title in all_titles:
        old_u = old_by_title.get(title)
        new_u = new_by_title.get(title)
        if old_u and not new_u:
            units_diff.append({"kind": "removed", "unit": old_u})
        elif new_u and not old_u:
            units_diff.append({"kind": "added", "unit": new_u})
        else:
            unit_changes = {}
            for field in ("title", "content", "hours"):
                ov = old_u.get(field, "")
                nv = new_u.get(field, "")
                if ov != nv:
                    unit_changes[field] = {"old": ov, "new": nv}
            if unit_changes:
                units_diff.append({"kind": "changed", "unit": new_u, "changes": unit_changes})
            else:
                units_diff.append({"kind": "unchanged", "unit": new_u})
    return {"kind": "units", "units": units_diff}


def _build_course_diff(base: dict, proposed: dict) -> dict:
    """Build a structured diff for a course, suitable for template rendering."""
    diff = {
        "course_title": _diff_text_field(base.get("course_title", ""), proposed.get("course_title", "")),
        "course_code": _diff_text_field(base.get("course_code", ""), proposed.get("course_code", "")),
        "program": _diff_text_field(base.get("program", ""), proposed.get("program", "")),
        "lecture_hours": _diff_text_field(str(base.get("lecture_hours", "")), str(proposed.get("lecture_hours", ""))),
        "tutorial_hours": _diff_text_field(str(base.get("tutorial_hours", "")), str(proposed.get("tutorial_hours", ""))),
        "practical_hours": _diff_text_field(str(base.get("practical_hours", "")), str(proposed.get("practical_hours", ""))),
        "self_study": _diff_text_field(str(base.get("self_study", "")), str(proposed.get("self_study", ""))),
        "credits": _diff_text_field(str(base.get("credits", "")), str(proposed.get("credits", ""))),
        "course_type": _diff_text_field(base.get("course_type", ""), proposed.get("course_type", "")),
        "semester": _diff_text_field(str(base.get("semester", "")), str(proposed.get("semester", ""))),
        "tools_languages": _diff_text_field(base.get("tools_languages", ""), proposed.get("tools_languages", "")),
        "desirable_knowledge": _diff_text_field(base.get("desirable_knowledge", ""), proposed.get("desirable_knowledge", "")),
        "prelude": _diff_text_field(base.get("prelude", ""), proposed.get("prelude", "")),
        "objectives": _diff_list_field(base.get("objectives") or [], proposed.get("objectives") or []),
        "course_outcomes": _diff_list_field(base.get("course_outcomes") or [], proposed.get("course_outcomes") or []),
        "units": _diff_units_field(base.get("units") or [], proposed.get("units") or []),
        "lab_experiments": _diff_list_field(base.get("lab_experiments") or [], proposed.get("lab_experiments") or []),
        "text_books": _diff_list_field(base.get("text_books") or [], proposed.get("text_books") or []),
        "reference_books": _diff_list_field(base.get("reference_books") or [], proposed.get("reference_books") or []),
    }
    return diff
