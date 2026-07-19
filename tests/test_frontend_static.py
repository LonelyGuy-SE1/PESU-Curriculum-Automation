import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


LIVE_EDITOR = Path("frontend/live-editor/index.html")
LIVE_EDITOR_JS = Path("frontend/live-editor/live-editor.js")


def test_live_editor_script_parses():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = "new Function(require('fs').readFileSync('frontend/live-editor/live-editor.js', 'utf8'));"
    subprocess.run([node, "-e", script], check=True)


def test_versions_script_parses():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = "new Function(require('fs').readFileSync('frontend/versions/versions.js', 'utf8'));"
    subprocess.run([node, "-e", script], check=True)


def test_courses_script_parses():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = "new Function(require('fs').readFileSync('frontend/courses/courses.js', 'utf8'));"
    subprocess.run([node, "-e", script], check=True)


def test_live_editor_uses_safe_message_rendering():
    text = LIVE_EDITOR_JS.read_text()

    assert "function renderMessageContent" in text
    assert "marked.parse" in text
    assert "DOMPurify.sanitize" in text
    assert 'content: "Working..."' not in text


def test_live_editor_uses_external_assets():
    text = LIVE_EDITOR.read_text()

    assert '<link rel="stylesheet" href="live-editor.css" />' in text
    assert '<script src="live-editor.js" defer></script>' in text
    assert 'id="save-version"' in text
    assert 'id="restore-version"' in text
    assert "<style>" not in text
    assert "<script>" not in text


def test_versions_page_uses_snapshot_language():
    text = Path("frontend/versions/index.html").read_text()

    assert "Version History" in text
    assert "Open in Editor" in text


def test_preview_uses_external_assets():
    text = Path("frontend/preview/index.html").read_text()
    script = Path("frontend/preview/preview.js").read_text()

    assert '<link rel="stylesheet" href="preview.css" />' in text
    assert '<script src="preview.js" defer></script>' in text
    assert 'id="curriculum-year"' in text
    assert "curriculum_year" in script
    assert "localStorage" in script
    assert "<style>" not in text
    assert "<script>" not in text


def test_frontend_pages_are_foldered():
    assert Path("frontend/form/index.html").exists()
    assert Path("frontend/courses/index.html").exists()
    assert Path("frontend/preview/index.html").exists()
    assert Path("frontend/live-editor/index.html").exists()
    assert Path("frontend/versions/index.html").exists()
    assert Path("frontend/form/form.js").exists()
    assert Path("frontend/courses/courses.js").exists()
    assert Path("frontend/preview/preview.js").exists()
    assert Path("frontend/live-editor/live-editor.js").exists()
    assert Path("frontend/versions/versions.js").exists()


def test_old_frontend_urls_redirect():
    assert 'content="0;url=form/"' in Path("frontend/form.html").read_text()
    assert 'content="0;url=courses/"' in Path("frontend/courses.html").read_text()
    assert 'content="0;url=preview/"' in Path("frontend/preview.html").read_text()
    assert 'content="0;url=live-editor/"' in Path("frontend/live-editor.html").read_text()
    assert 'content="0;url=versions/"' in Path("frontend/versions.html").read_text()


def test_dockerfile_copies_frontend_site():
    text = Path("Dockerfile").read_text()

    assert "COPY frontend/ frontend/" in text
    assert "COPY frontend/images/" not in text


def test_dockerignore_keeps_frontend_site():
    text = Path(".dockerignore").read_text()

    assert "frontend/**" not in text


def test_frontend_routes_mount(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "")
    from app.main import app

    client = TestClient(app)
    expected = {
        "/": "PESU Curriculum Automation",
        "/form/": "Submit Course",
        "/courses/": "Courses",
        "/preview/": "Preview",
        "/live-editor/": "Agentic Editor",
        "/versions/": "Version History",
    }

    for path, title in expected.items():
        response = client.get(path)
        assert response.status_code == 200
        assert title in response.text
