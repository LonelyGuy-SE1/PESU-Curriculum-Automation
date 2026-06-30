import re

from app.supabase import supabase
from app.services.deterministic import compute_hours, compute_program, compute_course_type
from app.services.openrouter import call as llm

BOOK_ITEM = re.compile(r"\s+(?=\d+[.)]\s+)")
BOOK_START = re.compile(r"^\s*\d+[.)]\s*(.+)$")
BOOK_SPLIT = re.compile(r"(?<=\d{4}\.)\s+(?=[\"\u201c])")
WORD = re.compile(r"\w+")

SYS = """You refine PES University course submissions for the UG curriculum template.
Return only valid JSON. No markdown. No commentary.
Rules:
- Preserve the submitted course scope. Do not add advanced or unrelated topics.
- Correct spelling, casing, and grammar in the course title.
- Keep every field concise and curriculum-ready.
- Preserve every syllabus topic and subtopic from Raw Course Content.
- Do not summarize away, omit, replace, or simplify syllabus topics.
- Correct spelling and grammar in syllabus text without changing meaning.
- Do not invent course codes, books, references, departments, or credits.
- Generate missing tools, objectives, outcomes, and prelude from the submitted course scope.
- For tools/languages, use Preferred Tools / Languages when provided; otherwise identify course-specific tools, languages, platforms, or AI tools from Raw Course Content.
- Do not use canned defaults for tools/languages.
- For desirable knowledge, use only relevant knowledge from Previously Completed Courses. Return an empty string when none apply.
- Use 3 or 4 course objectives as direct action statements.
- Use 3 or 4 course outcomes as measurable learner achievements.
- Return exactly 4 units.
- Distribute every submitted syllabus topic and subtopic across those 4 units.
- Unit hours must sum to the supplied total unit hours.
- Generate laboratory experiments only when practical hours are non-zero.
- Copy and clean books from the submitted book fields only.
"""

SCHEMA = """{
  "course_title": "corrected course title",
  "prelude": "one short paragraph",
  "objectives": ["3 to 4 objectives"],
  "course_outcomes": ["3 to 4 measurable outcomes"],
  "units": [{"title": "Unit 1: Title", "content": "compact topic list", "hours": 14}],
  "lab_experiments": ["concise lab item"],
  "tools_languages": "course-specific tools, languages, platforms, or AI tools",
  "desirable_knowledge": "short text based only on previously completed courses, or empty string",
  "text_books": ["submitted text books only"],
  "reference_books": ["submitted reference books only"]
}"""


def _lines(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def _books(value) -> list[str]:
    books = []
    for line in _lines(value):
        for item in BOOK_ITEM.split(line):
            for part in BOOK_SPLIT.split(item):
                part = part.strip()
                if not part:
                    continue
                match = BOOK_START.match(part)
                if match:
                    books.append(match.group(1).strip())
                elif books and part == item:
                    books[-1] = f"{books[-1]} {part}".strip()
                else:
                    books.append(part)
    return books


def _words(text: str) -> int:
    return len(WORD.findall(text))


def _clean_part(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip(" \t-*\u2022")).strip()


def _split_parts(text: str) -> list[str]:
    lines = [_clean_part(line) for line in text.splitlines() if _clean_part(line)]
    if len(lines) >= 4:
        return lines
    compact = _clean_part(text)
    parts = [_clean_part(part) for part in re.split(r"(?<=[.!?])\s+", compact) if _clean_part(part)]
    if len(parts) >= 4:
        return parts
    words = compact.split()
    if not words:
        return []
    return [
        " ".join(words[(index * len(words)) // 4 : ((index + 1) * len(words)) // 4])
        for index in range(4)
    ]


def _four_units_from_raw(raw_content: str) -> list[dict]:
    parts = _split_parts(raw_content)
    if not parts:
        return []
    buckets = [[] for _ in range(4)]
    for index, part in enumerate(parts):
        buckets[min(index * 4 // len(parts), 3)].append(part)
    return [
        {"title": f"Unit {index + 1}", "content": " ".join(bucket).strip(), "hours": 0}
        for index, bucket in enumerate(buckets)
        if bucket
    ]


def _unit_text(unit: dict) -> str:
    title = str(unit.get("title", "")).strip()
    content = str(unit.get("content", "")).strip()
    if title and content:
        return f"{title}: {content}"
    return title or content


def _fit_four_units(units: list[dict], raw_content: str) -> list[dict]:
    raw = raw_content.strip()
    if raw and _words(" ".join(_unit_text(unit) for unit in units)) < _words(raw) * 0.8:
        return _four_units_from_raw(raw)
    if len(units) > 4:
        fourth = units[3].copy()
        fourth["content"] = " ".join(_unit_text(unit) for unit in units[3:]).strip()
        return units[:3] + [fourth]
    if len(units) == 4:
        return units
    if raw:
        return _four_units_from_raw(raw)
    return units


def _units(value) -> list[dict]:
    units = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        content = str(item.get("content", "")).strip()
        hours_raw = str(item.get("hours", "0"))
        hours = int("".join(ch for ch in hours_raw if ch.isdigit()) or 0)
        if title or content:
            units.append({"title": title, "content": content, "hours": hours})
    return units


def _assign_hours(units: list[dict], total_hours: int) -> list[dict]:
    if not units:
        return units
    if sum(unit["hours"] for unit in units) == total_hours:
        return units
    base, extra = divmod(total_hours, len(units))
    for index, unit in enumerate(units):
        unit["hours"] = base + (1 if index < extra else 0)
    return units


def _text(*values) -> str:
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text and text != "-":
                return text
    return ""


def _prior_course_titles(sub: dict) -> list[str]:
    semester = int(sub["semester"])
    if semester <= 1:
        return []
    rows = (
        supabase.table("refined_submissions")
        .select("submission_id,course_title,semester")
        .lt("semester", semester)
        .order("semester")
        .execute()
        .data
    )
    ids = [row["submission_id"] for row in rows if row.get("submission_id")]
    submissions = supabase.table("submissions").select("id,target_department").in_("id", ids).execute().data if ids else []
    departments = {row["id"]: row.get("target_department") for row in submissions}
    titles = []
    for row in rows:
        if departments.get(row.get("submission_id")) != sub.get("target_department"):
            continue
        title = str(row.get("course_title") or "").strip()
        if title and title not in titles:
            titles.append(title)
    return titles


def _desirable(value, prior_courses: list[str]) -> str:
    if not prior_courses:
        return ""
    return _text(value)


def _courses_text(courses: list[str]) -> str:
    return "\n".join(f"- {course}" for course in courses) if courses else "None"


def build_refined_payload(sub: dict, out: dict, prior_courses: list[str] | None = None) -> dict:
    out = out or {}
    prior_courses = prior_courses or []
    det = compute_hours(sub["credit_category"])
    total_unit_hours = det["lecture_hours"] * 14
    units = _assign_hours(_fit_four_units(_units(out.get("units")), sub.get("raw_course_content") or ""), total_unit_hours)

    objectives = _lines(out.get("objectives"))[:4]
    course_outcomes = _lines(out.get("course_outcomes"))[:4] or objectives

    return {
        "submission_id": sub["id"],
        "semester": int(sub["semester"]),
        "course_code": "",
        "course_title": _text(out.get("course_title"), sub["course_title"]),
        "program": compute_program(sub["target_department"]),
        "course_type": compute_course_type(sub["credit_category"]),
        **det,
        "prelude": _text(out.get("prelude"), f"This course covers {sub['course_title'].strip()}."),
        "objectives": objectives,
        "course_outcomes": course_outcomes,
        "units": units,
        "lab_experiments": _lines(out.get("lab_experiments"))[:10] if det["practical_hours"] else [],
        "tools_languages": _text(out.get("tools_languages"), sub.get("preferred_tools")),
        "desirable_knowledge": _desirable(out.get("desirable_knowledge"), prior_courses),
        "text_books": _books(sub["text_books"]),
        "reference_books": _books(sub.get("reference_books")),
        "status": "refined",
    }


def refine(submission_id: int):
    sub = supabase.table("submissions").select("*").eq("id", submission_id).single().execute().data
    det = compute_hours(sub["credit_category"])
    ctype = compute_course_type(sub["credit_category"])
    total_unit_hours = det["lecture_hours"] * 14
    prior_courses = _prior_course_titles(sub)

    prompt = f"""Return JSON matching this schema. Include every key:
{SCHEMA}

Course Title: {sub["course_title"]}
Offering Department: {sub["offering_department"]}
Target Department: {sub["target_department"]}
Semester: {sub["semester"]}
Credit Category: {sub["credit_category"]}
Course Type: {ctype}
Weekly Hours: L {det["lecture_hours"]}, T {det["tutorial_hours"]}, P {det["practical_hours"]}, S {det["self_study"]}, C {det["credits"]}
Total Unit Hours: {total_unit_hours}
Raw Course Content:
{sub["raw_course_content"]}

Previously Completed Courses:
{_courses_text(prior_courses)}

Text Books:
{sub["text_books"]}

Reference Books:
{sub.get("reference_books") or "-"}

Preferred Tools / Languages:
{sub.get("preferred_tools") or "-"}"""

    out = llm(SYS, prompt)
    merged = build_refined_payload(sub, out, prior_courses)

    existing = supabase.table("refined_submissions").select("id").eq("submission_id", submission_id).execute().data
    if existing:
        supabase.table("refined_submissions").update(merged).eq("submission_id", submission_id).execute()
    else:
        supabase.table("refined_submissions").insert(merged).execute()

    supabase.table("submissions").update({"status": "refined"}).eq("id", submission_id).execute()

    return merged
