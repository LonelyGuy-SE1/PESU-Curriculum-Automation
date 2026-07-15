from collections.abc import Callable
from dataclasses import dataclass
import base64
import json
import re
from urllib.parse import quote_plus

import httpx
from weasyprint import HTML

from app.services.curriculum import create_version_snapshot, draft_record, load_agent_draft, load_document_draft, ordered_courses, refined_course, selected_curriculum_year
from app.services.diffing import diff_course
from app.supabase import supabase


def _markdown_to_html(md: str) -> str:
    """Convert basic markdown to HTML for PDF generation."""
    html = md
    # Headers
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    # Bold
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    # Italic
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    # Code inline
    html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
    # Code blocks
    html = re.sub(r'```(\w+)?\n(.+?)```', r'<pre><code class="language-\1">\2</code></pre>', html, flags=re.DOTALL)
    # Links
    html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2" target="_blank">\1</a>', html)
    # Unordered lists
    html = re.sub(r'^\- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(<li>.*?</li>\n)+', r'<ul>\n\g<0></ul>', html)
    # Tables (basic)
    # Split lines
    lines = html.split('\n')
    in_table = False
    result = []
    for line in lines:
        if line.strip().startswith('|') and '|' in line[1:]:
            if not in_table:
                result.append('<table>')
                in_table = True
            cells = [c.strip() for c in line.strip('|').split('|')]
            tag = 'th' if not in_table or not result[-1].startswith('<table>') else 'td'
            if len(result) == 1 and result[-1] == '<table>':
                tag = 'th'
            result.append('<tr>' + ''.join(f'<{tag}>{c}</{tag}>' for c in cells) + '</tr>')
        else:
            if in_table:
                result.append('</table>')
                in_table = False
            result.append(line)
    if in_table:
        result.append('</table>')
    html = '\n'.join(result)
    # Paragraphs
    lines = html.split('\n')
    result = []
    in_p = False
    for line in lines:
        if line.strip() and not line.startswith('<') and not line.startswith('</'):
            if not in_p:
                result.append('<p>')
                in_p = True
            result.append(line)
        else:
            if in_p:
                result.append('</p>')
                in_p = False
            result.append(line)
    if in_p:
        result.append('</p>')
    return '\n'.join(result)


ToolHandler = Callable[[dict], dict]


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    parameters: dict
    handler: ToolHandler

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def list_tool_schemas() -> list[dict]:
    return [tool.schema() for tool in TOOLS.values()]


def call_tool(name: str, arguments: dict | None = None) -> dict:
    tool = TOOLS.get(name)
    if not tool:
        raise LookupError("Agent tool not found")
    return tool.handler(arguments or {})


def _require_int(arguments: dict, key: str) -> int:
    value = arguments.get(key)
    if value is None:
        raise ValueError(f"{key} is required")
    return int(value)


def _require_dict(arguments: dict, key: str) -> dict:
    value = arguments.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _get_current_course(arguments: dict) -> dict:
    return {"course": refined_course(_require_int(arguments, "refined_id"))}


def _get_course_fields(arguments: dict) -> dict:
    """Get specific field groups from a course. More efficient than full course JSON."""
    refined_id = _require_int(arguments, "refined_id")
    fields = arguments.get("fields")
    if not isinstance(fields, list) or not fields:
        raise ValueError("fields must be a non-empty array of field names")
    
    course = refined_course(refined_id)
    result = {"refined_id": refined_id}
    for field in fields:
        if field in course:
            result[field] = course[field]
        else:
            result[field] = None
    return result


def _get_course_codes(arguments: dict) -> dict:
    """Get lightweight course identifiers: refined_id, course_code, course_title, semester."""
    refined_id = _require_int(arguments, "refined_id")
    course = refined_course(refined_id)
    return {
        "refined_id": refined_id,
        "course_code": course.get("course_code"),
        "course_title": course.get("course_title"),
        "semester": course.get("semester"),
        "program": course.get("program"),
    }


def _get_course_syllabus(arguments: dict) -> dict:
    """Get syllabus content: units, objectives, course_outcomes."""
    refined_id = _require_int(arguments, "refined_id")
    course = refined_course(refined_id)
    return {
        "refined_id": refined_id,
        "units": course.get("units"),
        "objectives": course.get("objectives"),
        "course_outcomes": course.get("course_outcomes"),
    }


def _get_course_textbooks(arguments: dict) -> dict:
    """Get textbook fields: text_books, reference_books."""
    refined_id = _require_int(arguments, "refined_id")
    course = refined_course(refined_id)
    return {
        "refined_id": refined_id,
        "text_books": course.get("text_books"),
        "reference_books": course.get("reference_books"),
    }


def _get_course_deterministic(arguments: dict) -> dict:
    """Get deterministic fields (program, hours, credits, course_type) — these are agent-protected."""
    refined_id = _require_int(arguments, "refined_id")
    course = refined_course(refined_id)
    return {
        "refined_id": refined_id,
        "program": course.get("program"),
        "lecture_hours": course.get("lecture_hours"),
        "tutorial_hours": course.get("tutorial_hours"),
        "practical_hours": course.get("practical_hours"),
        "self_study": course.get("self_study"),
        "credits": course.get("credits"),
        "course_type": course.get("course_type"),
    }


def _get_course_lab(arguments: dict) -> dict:
    """Get lab experiments and tools/languages."""
    refined_id = _require_int(arguments, "refined_id")
    course = refined_course(refined_id)
    return {
        "refined_id": refined_id,
        "lab_experiments": course.get("lab_experiments"),
        "tools_languages": course.get("tools_languages"),
    }


def _diff_course_json(arguments: dict) -> dict:
    return diff_course(_require_dict(arguments, "current"), _require_dict(arguments, "proposed"))


def _create_course_draft(arguments: dict) -> dict:
    record = draft_record(
        _require_int(arguments, "refined_id"),
        _require_dict(arguments, "fields"),
        str(arguments.get("reason") or ""),
    )
    draft = supabase.table("agent_drafts").insert(record).execute().data[0]
    return {"draft": draft}


def _get_curriculum_json(arguments: dict) -> dict:
    query = supabase.table("refined_submissions").select("*").neq("status", "archived")
    if arguments.get("semester") is not None:
        query = query.eq("semester", int(arguments["semester"]))
    return {"courses": ordered_courses(query.execute().data)}


def _create_document_draft(arguments: dict) -> dict:
    courses = arguments.get("courses")
    if not isinstance(courses, list) or not courses:
        raise ValueError("courses must be a non-empty array")

    records = []
    for course in courses:
        if not isinstance(course, dict):
            raise ValueError("each course must be an object")
        records.append(draft_record(int(course.get("refined_id")), _require_dict(course, "fields"), str(arguments.get("reason") or "")))

    summaries = [record["diff_summary"] for record in records]
    document_summary = {
        "courses_changed": len(records),
        "courses_with_removed_topics": sum(1 for summary in summaries if summary.get("topics_removed")),
        "courses_with_protected_changes": sum(1 for summary in summaries if summary.get("protected_changes")),
        "max_syllabus_change_percent": max((summary.get("syllabus_change_percent") or 0 for summary in summaries), default=0),
    }
    document = (
        supabase.table("agent_document_drafts")
        .insert(
            {
                "curriculum_version_id": arguments.get("curriculum_version_id"),
                "uploaded_document_id": str(arguments.get("uploaded_document_id") or "").strip(),
                "diff_summary": document_summary,
                "change_reason": str(arguments.get("reason") or "").strip(),
                "status": "blocked" if document_summary["courses_with_protected_changes"] else "proposed",
            }
        )
        .execute()
        .data[0]
    )
    for record in records:
        record["document_draft_id"] = document["id"]
    drafts = supabase.table("agent_drafts").insert(records).execute().data
    return {"document_draft": document, "drafts": drafts}


def _get_course_draft(arguments: dict) -> dict:
    return {"draft": load_agent_draft(_require_int(arguments, "draft_id"))}


def _get_document_draft(arguments: dict) -> dict:
    return load_document_draft(_require_int(arguments, "document_draft_id"))


def _get_preview_url(arguments: dict) -> dict:
    kind = str(arguments.get("kind") or "")
    item_id = _require_int(arguments, "id")
    paths = {
        "course": f"/api/preview/course/{item_id}",
        "draft": f"/api/agent/drafts/{item_id}/preview",
        "document_draft": f"/api/agent/document-drafts/{item_id}/preview",
    }
    if kind not in paths:
        raise ValueError("kind must be course, draft, or document_draft")
    return {"url": paths[kind]}


def _list_courses(arguments: dict) -> dict:
    query = supabase.table("refined_submissions").select("id,semester,course_code,course_title").neq("status", "archived")
    if arguments.get("semester") is not None:
        query = query.eq("semester", int(arguments["semester"]))
    rows = query.execute().data
    rows.sort(key=lambda row: (int(row.get("semester") or 0), str(row.get("course_code") or ""), int(row.get("id") or 0)))
    return {"courses": rows}


def _fetch_url(arguments: dict) -> dict:
    url = str(arguments.get("url") or "").strip()
    if not url:
        raise ValueError("url is required")
    resp = httpx.get(url, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    text = resp.text[:15000]
    return {"url": url, "text": text, "chars": len(text)}


def _web_search(arguments: dict) -> dict:
    """Search the web using DuckDuckGo's HTML endpoint and return top results."""
    query = str(arguments.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    num_results = int(arguments.get("num_results") or 5)
    num_results = min(max(num_results, 1), 10)

    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    resp = httpx.get(url, timeout=15, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()

    # Parse results from DuckDuckGo HTML
    html = resp.text
    results = []
    # Pattern for result snippets
    result_pattern = re.compile(r'class="result__snippet">(.*?)</a>', re.DOTALL)
    title_pattern = re.compile(r'class="result__title">.*?>(.*?)</a>', re.DOTALL)
    url_pattern = re.compile(r'class="result__url">.*?>(.*?)</a>', re.DOTALL)

    snippets = result_pattern.findall(html)
    titles = title_pattern.findall(html)
    urls = url_pattern.findall(html)

    for i in range(min(num_results, len(snippets))):
        title = re.sub(r"<[^>]+>", "", titles[i] if i < len(titles) else "").strip()
        snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()
        link = re.sub(r"<[^>]+>", "", urls[i] if i < len(urls) else "").strip()
        if title or snippet:
            results.append({"title": title, "snippet": snippet[:300], "url": link})

    return {"query": query, "results": results}


def _create_report(arguments: dict) -> dict:
    session_id = _require_int(arguments, "session_id")
    content = str(arguments.get("content") or "").strip()
    if not content:
        raise ValueError("content is required")
    filename = str(arguments.get("filename") or "report.md").strip()
    fmt = str(arguments.get("format") or "markdown").strip().lower()
    if fmt not in ("markdown", "pdf"):
        raise ValueError("format must be 'markdown' or 'pdf'")
    
    if fmt == "pdf":
        # Convert markdown to HTML then to PDF
        import subprocess
        import tempfile
        import os
        
        # Simple markdown to HTML conversion
        html_content = _markdown_to_html(content)
        html_full = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1, h2, h3 {{ color: #00377b; }}
        table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #f0f2f5; }}
        code {{ background: #f3f4f6; padding: 2px 4px; border-radius: 3px; }}
        pre {{ background: #f3f4f6; padding: 10px; overflow-x: auto; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""
        
        # Use weasyprint to generate PDF
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_full, base_url=".").write_pdf()
        
        if filename.endswith(".md"):
            filename = filename[:-3] + ".pdf"
        elif not filename.endswith(".pdf"):
            filename = filename + ".pdf"
        
        content_type = "application/pdf"
        size_bytes = len(pdf_bytes)
        extracted_text = f"[PDF file - {size_bytes} bytes]"
        content_base64 = base64.b64encode(pdf_bytes).decode()
    else:
        pdf_bytes = None
        content_type = "text/markdown"
        size_bytes = len(content.encode())
        extracted_text = content
        content_base64 = ""
    
    row = (
        supabase.table("chat_attachments")
        .insert({
            "session_id": session_id,
            "filename": filename,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "extracted_text": extracted_text,
            "content_base64": content_base64,
            "status": "ready",
        })
        .execute()
        .data[0]
    )

    return {"attachment": {"id": row["id"], "filename": row["filename"], "chars": size_bytes, "format": fmt}}


def _attachment_text(arguments: dict) -> dict:
    session_id = _require_int(arguments, "session_id")
    ids = [int(value) for value in arguments.get("attachment_ids") or []]
    if not ids:
        raise ValueError("attachment_ids is required")
    rows = (
        supabase.table("chat_attachments")
        .select("id,filename,status,error,extracted_text")
        .eq("session_id", session_id)
        .in_("id", ids)
        .execute()
        .data
    )
    return {"attachments": rows}


def _create_curriculum_version(arguments: dict) -> dict:
    name = str(arguments.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    version = create_version_snapshot(name)
    return {"version": version}


def _define_specialization(arguments: dict) -> dict:
    semester = _require_int(arguments, "semester")
    name = str(arguments.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    letter = str(arguments.get("letter") or "").strip().upper()
    if not letter:
        existing = supabase.table("specialization_definitions").select("letter").eq("semester", semester).execute().data
        used = {row["letter"] for row in existing}
        for candidate in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if candidate not in used:
                letter = candidate
                break
        if not letter:
            raise ValueError("No free specialization letter available for this semester")
    academic_year = str(arguments.get("academic_year") or "").strip()
    key = str(arguments.get("key") or "").strip().upper()
    if not key:
        key = name.split("(")[-1].rstrip(")") if "(" in name else name[:3].upper()
    row = supabase.table("specialization_definitions").insert(
        {"semester": semester, "letter": letter, "name": name, "key": key, "academic_year": academic_year}
    ).execute().data[0]
    return {"specialization": row}


def _list_specializations(arguments: dict) -> dict:
    query = supabase.table("specialization_definitions").select("*")
    if arguments.get("semester") is not None:
        query = query.eq("semester", int(arguments["semester"]))
    return {"specializations": query.order("semester").order("letter").execute().data}


def _assign_elective_to_tracks(arguments: dict) -> dict:
    refined_id = _require_int(arguments, "refined_id")
    spec_ids = arguments.get("specialization_ids")
    if not isinstance(spec_ids, list) or not spec_ids:
        raise ValueError("specialization_ids must be a non-empty array")
    created = 0
    for spec_id in spec_ids:
        existing = (
            supabase.table("course_specialization_assignments")
            .select("id")
            .eq("refined_id", refined_id)
            .eq("specialization_id", int(spec_id))
            .execute()
            .data
        )
        if not existing:
            supabase.table("course_specialization_assignments").insert(
                {"refined_id": refined_id, "specialization_id": int(spec_id)}
            ).execute()
            created += 1
    supabase.table("refined_submissions").update({"is_elective": True}).eq("id", refined_id).execute()
    return {"assignments_created": created}


def _remove_elective_from_tracks(arguments: dict) -> dict:
    refined_id = _require_int(arguments, "refined_id")
    spec_ids = arguments.get("specialization_ids")
    if not isinstance(spec_ids, list) or not spec_ids:
        raise ValueError("specialization_ids must be a non-empty array")
    removed = 0
    for spec_id in spec_ids:
        result = (
            supabase.table("course_specialization_assignments")
            .delete()
            .eq("refined_id", refined_id)
            .eq("specialization_id", int(spec_id))
            .execute()
        )
        removed += len(result.data or [])
    return {"assignments_removed": removed}


def _get_course_assignments(arguments: dict) -> dict:
    refined_id = _require_int(arguments, "refined_id")
    assignments = (
        supabase.table("course_specialization_assignments")
        .select("*, specialization_definitions(*)")
        .eq("refined_id", refined_id)
        .execute()
        .data
    )
    return {"refined_id": refined_id, "assignments": assignments}


def _update_deterministic_fields(arguments: dict) -> dict:
    from app.services.diffing import PROTECTED_FIELDS

    refined_id = _require_int(arguments, "refined_id")
    fields = _require_dict(arguments, "fields")
    protected = {key: value for key, value in fields.items() if key in PROTECTED_FIELDS}
    if not protected:
        raise ValueError("No deterministic fields provided. Use create_course_draft for other fields.")
    record = draft_record(refined_id, protected, str(arguments.get("reason") or "Explicit user request to change deterministic fields"))
    record["status"] = "blocked"
    draft = supabase.table("agent_drafts").insert(record).execute().data[0]
    return {
        "draft": draft,
        "warning": "This draft modifies deterministic fields (program, hours, credits, course_type). The user must explicitly approve it in the Review panel before it is applied.",
    }


def _signal_done(arguments: dict) -> dict:
    summary = str(arguments.get("summary") or "").strip()
    if not summary:
        raise ValueError("summary is required")
    return {"done": True, "summary": summary}


OBJECT = {"type": "object", "additionalProperties": False}

TOOLS: dict[str, AgentTool] = {
    "get_current_course_json": AgentTool(
        "get_current_course_json",
        "Read the current template-ready JSON for one refined course.",
        {**OBJECT, "properties": {"refined_id": {"type": "integer"}}, "required": ["refined_id"]},
        _get_current_course,
    ),
    "get_course_codes": AgentTool(
        "get_course_codes",
        "Read lightweight course identifiers (refined_id, course_code, course_title, semester, program). Use for listing or quick lookups.",
        {**OBJECT, "properties": {"refined_id": {"type": "integer"}}, "required": ["refined_id"]},
        _get_course_codes,
    ),
    "get_course_syllabus": AgentTool(
        "get_course_syllabus",
        "Read syllabus content: units, objectives, course_outcomes.",
        {**OBJECT, "properties": {"refined_id": {"type": "integer"}}, "required": ["refined_id"]},
        _get_course_syllabus,
    ),
    "get_course_textbooks": AgentTool(
        "get_course_textbooks",
        "Read textbook fields: text_books, reference_books.",
        {**OBJECT, "properties": {"refined_id": {"type": "integer"}}, "required": ["refined_id"]},
        _get_course_textbooks,
    ),
    "get_course_deterministic": AgentTool(
        "get_course_deterministic",
        "Read deterministic/protected fields: program, lecture_hours, tutorial_hours, practical_hours, self_study, credits, course_type. These cannot be changed by the agent.",
        {**OBJECT, "properties": {"refined_id": {"type": "integer"}}, "required": ["refined_id"]},
        _get_course_deterministic,
    ),
    "get_course_lab": AgentTool(
        "get_course_lab",
        "Read lab experiments and tools/languages.",
        {**OBJECT, "properties": {"refined_id": {"type": "integer"}}, "required": ["refined_id"]},
        _get_course_lab,
    ),
    "get_course_fields": AgentTool(
        "get_course_fields",
        "Read arbitrary specific fields from a course. Provide a list of field names. More efficient than fetching full JSON when you only need a subset.",
        {
            **OBJECT,
            "properties": {
                "refined_id": {"type": "integer"},
                "fields": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            },
            "required": ["refined_id", "fields"],
        },
        _get_course_fields,
    ),
    "diff_course_json": AgentTool(
        "diff_course_json",
        "Compare two course JSON objects and return patch operations, changed percent, and syllabus topic changes.",
        {**OBJECT, "properties": {"current": {"type": "object"}, "proposed": {"type": "object"}}, "required": ["current", "proposed"]},
        _diff_course_json,
    ),
    "create_course_draft": AgentTool(
        "create_course_draft",
        "Create a human-reviewable draft for one course. This never applies changes to refined_submissions.",
        {
            **OBJECT,
            "properties": {
                "refined_id": {"type": "integer"},
                "fields": {"type": "object"},
                "reason": {"type": "string"},
            },
            "required": ["refined_id", "fields"],
        },
        _create_course_draft,
    ),
    "get_curriculum_json": AgentTool(
        "get_curriculum_json",
        "Read template-ready JSON for the full curriculum, optionally filtered by semester.",
        {**OBJECT, "properties": {"semester": {"type": "integer", "minimum": 1, "maximum": 8}}},
        _get_curriculum_json,
    ),
    "create_document_draft": AgentTool(
        "create_document_draft",
        "Create one human-reviewable document draft containing proposed changes for multiple courses. This never applies changes.",
        {
            **OBJECT,
            "properties": {
                "courses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"refined_id": {"type": "integer"}, "fields": {"type": "object"}},
                        "required": ["refined_id", "fields"],
                        "additionalProperties": False,
                    },
                },
                "reason": {"type": "string"},
                "uploaded_document_id": {"type": "string"},
                "curriculum_version_id": {"type": "integer"},
            },
            "required": ["courses"],
        },
        _create_document_draft,
    ),
    "get_course_draft": AgentTool(
        "get_course_draft",
        "Read one staged course draft and its diff summary.",
        {**OBJECT, "properties": {"draft_id": {"type": "integer"}}, "required": ["draft_id"]},
        _get_course_draft,
    ),
    "get_document_draft": AgentTool(
        "get_document_draft",
        "Read one staged document draft and all linked course drafts.",
        {**OBJECT, "properties": {"document_draft_id": {"type": "integer"}}, "required": ["document_draft_id"]},
        _get_document_draft,
    ),
    "get_preview_url": AgentTool(
        "get_preview_url",
        "Return the preview URL for a course, course draft, or document draft.",
        {
            **OBJECT,
            "properties": {
                "kind": {"type": "string", "enum": ["course", "draft", "document_draft"]},
                "id": {"type": "integer"},
            },
            "required": ["kind", "id"],
        },
        _get_preview_url,
    ),
    "list_courses": AgentTool(
        "list_courses",
        "List refined course IDs and titles, optionally filtered by semester.",
        {**OBJECT, "properties": {"semester": {"type": "integer", "minimum": 1, "maximum": 8}}},
        _list_courses,
    ),
    "get_attachment_text": AgentTool(
        "get_attachment_text",
        "Read extracted text for uploaded chat attachments within a chat session.",
        {
            **OBJECT,
            "properties": {
                "session_id": {"type": "integer"},
                "attachment_ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["session_id", "attachment_ids"],
        },
        _attachment_text,
    ),
    "fetch_url": AgentTool(
        "fetch_url",
        "Fetch a public URL and return its text content. Use to read web pages, public documents, and online resources.",
        {**OBJECT, "properties": {"url": {"type": "string"}}, "required": ["url"]},
        _fetch_url,
    ),
    "web_search": AgentTool(
        "web_search",
        "Search the web and return top results with titles, snippets, and URLs. Use for finding current information, documentation, or references.",
        {
            **OBJECT,
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
            },
            "required": ["query"],
        },
        _web_search,
    ),
    "create_report": AgentTool(
        "create_report",
        "Save a generated document (report, comparison, summary, etc.) as a chat attachment accessible to the user. Use after reading source documents and generating new content. Supports markdown (.md) or PDF (.pdf) output.",
        {
            **OBJECT,
            "properties": {
                "session_id": {"type": "integer"},
                "content": {"type": "string", "description": "Full report/document content in markdown format"},
                "filename": {"type": "string", "description": "Filename including extension, e.g. comparison-report.md or comparison-report.pdf"},
                "format": {"type": "string", "enum": ["markdown", "pdf"], "default": "markdown", "description": "Output format: markdown or pdf"},
            },
            "required": ["session_id", "content"],
        },
        _create_report,
    ),
    "create_curriculum_version": AgentTool(
        "create_curriculum_version",
        "Create a named curriculum version snapshot (like a git commit). Use to checkpoint the curriculum state after a set of changes. Provide a descriptive name like 'feat: add CS201 lab experiments' or 'fix: correct credit hours for ECE301'.",
        {
            **OBJECT,
            "properties": {
                "name": {"type": "string", "description": "Descriptive version name (conventional commit style encouraged)"},
            },
            "required": ["name"],
        },
        _create_curriculum_version,
    ),
    "define_specialization": AgentTool(
        "define_specialization",
        "Create a specialization track (e.g. Machine Intelligence and Data Science) for a given semester. The letter (A, B, C...) is auto-assigned if omitted. Used to set up the elective specialization brackets.",
        {
            **OBJECT,
            "properties": {
                "semester": {"type": "integer", "minimum": 1, "maximum": 8, "description": "Semester the specialization applies to (5 or 6 for electives)"},
                "name": {"type": "string", "description": "Full specialization name, e.g. 'Machine Intelligence and Data Science (MIDS)'"},
                "letter": {"type": "string", "description": "Optional letter label (A, B, C). Auto-assigned if omitted."},
                "key": {"type": "string", "description": "Optional short key (SCC, MIDS, CSCS). Derived from name if omitted."},
                "academic_year": {"type": "string", "description": "Optional academic year batch, e.g. 2025-26"},
            },
            "required": ["semester", "name"],
        },
        _define_specialization,
    ),
    "list_specializations": AgentTool(
        "list_specializations",
        "List specialization track definitions, optionally filtered by semester. Use to discover which tracks exist before assigning electives.",
        {
            **OBJECT,
            "properties": {"semester": {"type": "integer", "minimum": 1, "maximum": 8}},
        },
        _list_specializations,
    ),
    "assign_elective_to_tracks": AgentTool(
        "assign_elective_to_tracks",
        "Categorize an elective course into one or more specialization tracks by their specialization_id. Also marks the course as an elective. Use after determining (e.g. via AI analysis) which tracks the course belongs to.",
        {
            **OBJECT,
            "properties": {
                "refined_id": {"type": "integer"},
                "specialization_ids": {"type": "array", "items": {"type": "integer"}, "description": "Specialization track IDs to assign the elective to"},
            },
            "required": ["refined_id", "specialization_ids"],
        },
        _assign_elective_to_tracks,
    ),
    "remove_elective_from_tracks": AgentTool(
        "remove_elective_from_tracks",
        "Remove an elective course from one or more specialization tracks.",
        {
            **OBJECT,
            "properties": {
                "refined_id": {"type": "integer"},
                "specialization_ids": {"type": "array", "items": {"type": "integer"}, "description": "Specialization track IDs to remove the elective from"},
            },
            "required": ["refined_id", "specialization_ids"],
        },
        _remove_elective_from_tracks,
    ),
    "get_course_assignments": AgentTool(
        "get_course_assignments",
        "Return which specialization tracks a course currently belongs to, including the track definitions.",
        {
            **OBJECT,
            "properties": {"refined_id": {"type": "integer"}},
            "required": ["refined_id"],
        },
        _get_course_assignments,
    ),
    "update_deterministic_fields": AgentTool(
        "update_deterministic_fields",
        "Create a reviewable draft that changes deterministic/protected fields (program, lecture_hours, tutorial_hours, practical_hours, self_study, credits, course_type). This is the ONLY way to modify those fields. The resulting draft is blocked until the user explicitly approves it in the Review panel. Always confirm with the user before calling this.",
        {
            **OBJECT,
            "properties": {
                "refined_id": {"type": "integer"},
                "fields": {"type": "object", "description": "Protected fields to change, e.g. {\"credits\": 5, \"lecture_hours\": 4}"},
                "reason": {"type": "string"},
            },
            "required": ["refined_id", "fields"],
        },
        _update_deterministic_fields,
    ),
    "signal_done": AgentTool(
        "signal_done",
        "Signal that the agent has completed the user's request. Provide a concise summary of what was accomplished. This ends the agent's turn.",
        {
            **OBJECT,
            "properties": {
                "summary": {"type": "string", "description": "Brief summary of what was done, e.g. 'Created draft for CS201 adding Unit 5 on Graph Algorithms'"},
            },
            "required": ["summary"],
        },
        _signal_done,
    ),
}
