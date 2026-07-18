import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from jinja2.ext import do
from markupsafe import Markup, escape

APP_DIR = Path(__file__).resolve().parent


def _find_frontend_dir() -> Path:
    app_root = APP_DIR.parent
    candidates = (
        app_root / "frontend",
        app_root.parent / "frontend",
        app_root.parent.parent / "frontend",
        Path("/frontend"),
    )
    result = next((p for p in candidates if p.exists()), None)
    if result is None:
        raise RuntimeError("Frontend directory not found; cannot resolve image assets for PDF rendering")
    return result


FRONTEND_DIR = _find_frontend_dir()
templates = Environment(loader=FileSystemLoader(APP_DIR / "templates"), autoescape=select_autoescape(["html", "xml"]), extensions=[do])
URL_RE = re.compile(r"https?://[^\s<>()]+")
YEAR_RE = re.compile(r"\d{4}")


def linkify(value: str) -> Markup:
    text = str(value or "")
    parts = []
    last = 0
    for match in URL_RE.finditer(text):
        raw_url = match.group(0)
        url = raw_url.rstrip(".,;:)]}")
        trailing = raw_url[len(url) :]
        safe_url = escape(url)
        parts.append(escape(text[last : match.start()]))
        parts.append(Markup(f'<a class="resource-link" href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_url}</a>'))
        parts.append(escape(trailing))
        last = match.end()
    parts.append(escape(text[last:]))
    return Markup("".join(str(part) for part in parts))


def batch_start_year(semester, curriculum_year: str) -> int | None:
    match = YEAR_RE.search(str(curriculum_year or ""))
    if not match:
        return None
    try:
        sem = int(semester)
    except (TypeError, ValueError):
        return None
    return int(match.group()) - ((sem - 1) // 2)


def batch_label(semester, curriculum_year: str) -> str:
    start = batch_start_year(semester, curriculum_year)
    return f"({start}-{(start + 4) % 100:02d} BATCH)" if start else ""


def course_code_for_year(value: str, semester, curriculum_year: str) -> str:
    code = str(value or "")
    start = batch_start_year(semester, curriculum_year)
    if not start or len(code) < 5 or code[:2] not in {"UE", "UZ"} or not code[2:4].isdigit():
        return code
    return f"{code[:2]}{start % 100:02d}{code[4:]}"


templates.filters["linkify"] = linkify
templates.filters["course_code_for_year"] = course_code_for_year
templates.globals["batch_label"] = batch_label

SEMESTER_NAMES = {
    "1": "I",
    "2": "II",
    "3": "III",
    "4": "IV",
    "5": "V",
    "6": "VI",
    "7": "VII",
    "8": "VIII",
}
templates.globals["SEMESTER_NAMES"] = SEMESTER_NAMES
