from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from postgrest.exceptions import APIError

from app import cache
from app.preview import build_course_preview, build_specialization_context
from app.rendering import templates
from app.services.curriculum import attach_submissions, DEFAULT_CURRICULUM_YEAR, invalidate_curriculum_cache, selected_curriculum_year, update_refined_fields
from app.services.diffing import build_course_diff, diff_course
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
    cached = cache.get("versions_list")
    if cached is not None:
        return {"versions": cached}
    try:
        rows = supabase.table("curriculum_versions").select("*").order("id", desc=True).execute().data
        version_ids = [row["id"] for row in rows]
        if version_ids:
            fs_rows = (
                supabase.table("finalized_submissions")
                .select("curriculum_version_id,refined_id,course_json")
                .in_("curriculum_version_id", version_ids)
                .execute()
                .data
            )
            count_map: dict[int, int] = {}
            version_courses: dict[int, dict[int, dict]] = {}
            for c in fs_rows:
                vid = c["curriculum_version_id"]
                count_map[vid] = count_map.get(vid, 0) + 1
                version_courses.setdefault(vid, {})[c["refined_id"]] = c.get("course_json") or {}
            for row in rows:
                row["course_count"] = count_map.get(row["id"], 0)
            current_rows = supabase.table("refined_submissions").select("*").in_("status", ["refined"]).execute().data
            current_rows = attach_submissions(current_rows)
            current_map = {row["id"]: build_course_preview(row) for row in current_rows}
            for row in rows:
                vid = row["id"]
                v_courses = version_courses.get(vid, {})
                has_changes = False
                for rid, v_json in v_courses.items():
                    c_json = current_map.get(rid, {})
                    if v_json != c_json:
                        has_changes = True
                        break
                row["has_changes"] = has_changes
        else:
            for row in rows:
                row["course_count"] = 0
                row["has_changes"] = False
    except APIError as exc:
        raise database_http_exception(exc) from exc
    cache.put("versions_list", rows, ttl=300)
    return {"versions": rows}


@router.patch("/versions/{version_id}")
def update_version(version_id: int, payload: dict):
    _version(version_id)
    updates = {}
    if "name" in payload:
        new_name = str(payload["name"]).strip()
        if new_name:
            existing = (
                supabase.table("curriculum_versions")
                .select("id")
                .eq("name", new_name)
                .neq("id", version_id)
                .limit(1)
                .execute()
                .data
            )
            if existing:
                raise HTTPException(status_code=400, detail="A version with this name already exists")
            updates["name"] = new_name
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
    cache.invalidate("versions_list")
    return {"version": row}


@router.post("/versions")
def create_version(payload: dict):
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Version name is required")

    try:
        existing = (
            supabase.table("curriculum_versions")
            .select("id")
            .eq("name", name)
            .limit(1)
            .execute()
            .data
        )
        if existing:
            raise HTTPException(status_code=400, detail="A version with this name already exists")

        rows = supabase.table("refined_submissions").select("*").in_("status", ["refined"]).execute().data
        rows = attach_submissions(rows)
        courses = [{"refined_id": row["id"], "course_json": build_course_preview(row)} for row in rows]

        latest = (
            supabase.table("curriculum_versions")
            .select("id")
            .order("id", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if latest:
            prev_fs = (
                supabase.table("finalized_submissions")
                .select("refined_id,course_json")
                .eq("curriculum_version_id", latest[0]["id"])
                .execute()
                .data
            )
            prev_map = {c["refined_id"]: c.get("course_json") or {} for c in prev_fs}
            if prev_map and all(
                prev_map.get(c["refined_id"]) == c["course_json"] for c in courses
            ):
                raise HTTPException(status_code=409, detail="No changes since last version")

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
    cache.invalidate("versions_list")
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
        if not rows:
            raise HTTPException(status_code=400, detail="This version has no saved courses. Restore aborted.")
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
        invalidate_curriculum_cache()
    except APIError as exc:
        raise database_http_exception(exc) from exc
    cache.invalidate("ver_preview:")
    cache.invalidate("versions_list")
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
    courses.sort(
        key=lambda course: (
            int(course.get("semester") or 0),
            str(course.get("course_code") or ""),
            str(course.get("course_title") or ""),
        )
    )
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
    _version(version_id)
    html = templates.get_template("jinja_sample.html").render(course=snapshot["course_json"], curriculum_year=selected_curriculum_year(curriculum_year), asset_root="/")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@router.get("/versions/{version_id}/preview")
def preview_version(version_id: int, diff: bool = Query(False), curriculum_year: str | None = Query(None)):
    try:
        _version(version_id)
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
        cache_key = f"ver_preview:{version_id}:clean:{selected_curriculum_year(curriculum_year)}"
        cached = cache.get(cache_key)
        if cached:
            return HTMLResponse(cached, headers={"Cache-Control": "public, max-age=30"})
        html = templates.get_template("jinja_sample.html").render(
            courses=version_courses,
            semester="",
            curriculum_year=selected_curriculum_year(curriculum_year),
            asset_root="/",
            show_summaries=True,
            **build_specialization_context(selected_curriculum_year(curriculum_year)),
        )
        cache.put(cache_key, html, ttl=120)
        return HTMLResponse(html, headers={"Cache-Control": "public, max-age=30"})

    # Diff mode: compare version against current refined submissions
    cache_key = f"ver_preview:{version_id}:diff:{selected_curriculum_year(curriculum_year)}"
    cached = cache.get(cache_key)
    if cached:
        return HTMLResponse(cached, headers={"Cache-Control": "public, max-age=30"})

    refined_ids = [v["refined_id"] for v in version_courses if "refined_id" in v]
    current_rows = supabase.table("refined_submissions").select("*").in_("id", refined_ids).execute().data if refined_ids else []
    current_rows = attach_submissions(current_rows)
    current = {row["id"]: build_course_preview(row) for row in current_rows}

    course_diffs = []
    for v_course in version_courses:
        refined_id = v_course.get("refined_id")
        current_course = current.get(refined_id)
        if current_course:
            base = dict(current_course)
            proposed = dict(v_course)
            if base == proposed:
                continue
            course_diff = build_course_diff(base, proposed)
            if any(v is not None for v in course_diff.values()):
                course_diffs.append({"base": base, "proposed": proposed, "course_diff": course_diff})

    html = templates.get_template("jinja_diff.html").render(
        course_diffs=course_diffs,
        curriculum_year=selected_curriculum_year(curriculum_year),
        asset_root="/",
    )
    cache.put(cache_key, html, ttl=120)
    return HTMLResponse(html, headers={"Cache-Control": "public, max-age=30"})
