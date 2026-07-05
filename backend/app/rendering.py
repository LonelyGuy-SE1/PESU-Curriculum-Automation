import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

APP_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = APP_DIR.parent.parent / "frontend"
templates = Environment(loader=FileSystemLoader(APP_DIR / "templates"), autoescape=select_autoescape(["html", "xml"]))
URL_RE = re.compile(r"https?://[^\s<>()]+")


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


templates.filters["linkify"] = linkify
