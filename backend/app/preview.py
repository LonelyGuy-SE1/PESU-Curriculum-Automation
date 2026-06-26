import json


def build_course_preview(row: dict) -> dict:
    content = json.loads(row.get("refined_content") or "{}")
    return {
        "course_code": str(content.get("course_code", "")),
        "course_title": str(content.get("course_title", "")),
        "program": str(content.get("program", "")),
        "lecture_hours": str(content.get("lecture_hours", 0)),
        "tutorial_hours": str(content.get("tutorial_hours", 0)),
        "practical_hours": str(content.get("practical_hours", 0)),
        "self_study": str(content.get("self_study", 0)),
        "credits": str(content.get("credits", 0)),
        "semester": str(content.get("semester", "")),
        "course_type": str(content.get("course_type", "")),
        "tools_languages": str(content.get("tools_languages", "")),
        "desirable_knowledge": str(content.get("desirable_knowledge", "")),
        "prelude": row.get("prelude") or content.get("prelude", ""),
        "objectives": row.get("objectives") or content.get("objectives", []),
        "units": content.get("units", []),
        "lab_experiments": content.get("lab_experiments", []),
    }