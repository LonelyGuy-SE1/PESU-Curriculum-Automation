from pathlib import Path
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient


FORM_HTML = Path("frontend/form/index.html")
FORM_CSS = Path("frontend/form/form.css")
FORM_JS = Path("frontend/form/form.js")


def test_form_page_loads():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("SENTRY_DSN", "")
    from app.main import app

    client = TestClient(app)
    response = client.get("/form/")
    assert response.status_code == 200
    assert "Course Submission" in response.text
    monkeypatch.undo()


def test_form_has_required_fields():
    html = FORM_HTML.read_text()
    assert 'id="faculty_email"' in html
    assert 'id="course_code"' in html
    assert 'id="course_title"' in html
    assert 'id="raw_course_content"' in html
    assert 'id="text_books"' in html


def test_email_field_not_required():
    html = FORM_HTML.read_text()
    for line in html.splitlines():
        if 'id="faculty_email"' in line:
            assert "required" not in line
            return
    pytest.fail("Email input not found")


def test_email_field_marked_optional():
    html = FORM_HTML.read_text()
    lines = html.splitlines()
    for i, line in enumerate(lines):
        if 'id="faculty_email"' in line:
            preceding = "\n".join(lines[max(0, i - 2):i + 1])
            assert "(optional)" in preceding
            return
    pytest.fail("Email input not found")


def test_course_code_field_required():
    html = FORM_HTML.read_text()
    for line in html.splitlines():
        if 'id="course_code"' in line:
            assert "required" in line
            return
    pytest.fail("Course code input not found")


def test_form_uses_external_assets():
    html = FORM_HTML.read_text()
    assert '<link rel="stylesheet" href="form.css" />' in html
    assert '<script src="form.js" defer></script>' in html
    assert "<style>" not in html


def test_form_has_optional_fields_marked():
    html = FORM_HTML.read_text()
    assert "optional" in html.lower()


def test_form_links_to_courses_and_preview():
    html = FORM_HTML.read_text()
    assert 'href="../courses/"' in html
    assert 'href="../preview/"' in html


def test_form_css_imports_shared():
    css = FORM_CSS.read_text()
    assert '@import "../shared.css"' in css


def test_form_js_no_native_confirm():
    js = FORM_JS.read_text()
    assert "confirm(" not in js


def test_backend_allows_empty_email():
    from app.models.submission import CourseSubmission

    submission = CourseSubmission(
        faculty_email="",
        course_code="UE25CS242B",
        course_title="Operating Systems",
        raw_course_content="Unit 1: Process management. Unit 2: Memory management. Unit 3: File systems. Unit 4: I/O systems. Unit 5: Deadlocks and synchronization.",
        text_books="Operating System Concepts, Silberschatz",
    )
    assert submission.faculty_email == ""


def test_backend_rejects_long_email():
    from app.models.submission import CourseSubmission
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CourseSubmission(
            faculty_email="a" * 255,
            course_code="UE25CS242B",
            course_title="Operating Systems",
            raw_course_content="Unit 1: Process management. Unit 2: Memory management. Unit 3: File systems. Unit 4: I/O systems. Unit 5: Deadlocks and synchronization.",
            text_books="Operating System Concepts, Silberschatz",
        )


def test_form_has_rule_accent():
    html = FORM_HTML.read_text()
    assert 'class="rule"' in html


def test_form_has_auth_guard():
    html = FORM_HTML.read_text()
    assert "auth-guard.js" in html


def test_shared_css_has_inter_font():
    import re

    css = Path("frontend/shared.css").read_text()
    assert "Outfit" in css
    urls = re.findall(r"url\(\s*['\"]?([^'\"\)]+)['\"]?\s*\)", css)
    assert any(urlparse(u).hostname == "fonts.googleapis.com" for u in urls)


def test_homepage_has_default_year():
    html = Path("frontend/index.html").read_text()
    assert "2025-2026" in html
    assert "DEFAULT_YEAR" in html
