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


def test_live_editor_uses_safe_message_rendering():
    text = LIVE_EDITOR_JS.read_text()

    assert "function renderMessageContent" in text
    assert ".innerHTML" not in text


def test_live_editor_uses_external_assets():
    text = LIVE_EDITOR.read_text()

    assert '<link rel="stylesheet" href="live-editor.css" />' in text
    assert '<script src="live-editor.js" defer></script>' in text
    assert "<style>" not in text
    assert "<script>" not in text


def test_preview_uses_external_assets():
    text = Path("frontend/preview/index.html").read_text()

    assert '<link rel="stylesheet" href="preview.css" />' in text
    assert '<script src="preview.js" defer></script>' in text
    assert "<style>" not in text
    assert "<script>" not in text


def test_frontend_pages_are_foldered():
    assert Path("frontend/form/index.html").exists()
    assert Path("frontend/preview/index.html").exists()
    assert Path("frontend/live-editor/index.html").exists()
    assert Path("frontend/form/form.js").exists()
    assert Path("frontend/preview/preview.js").exists()
    assert Path("frontend/live-editor/live-editor.js").exists()


def test_old_frontend_urls_redirect():
    assert 'content="0;url=form/"' in Path("frontend/form.html").read_text()
    assert 'content="0;url=preview/"' in Path("frontend/preview.html").read_text()
    assert 'content="0;url=live-editor/"' in Path("frontend/live-editor.html").read_text()


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
        "/form/": "Course Submission",
        "/preview/": "Curriculum Preview",
        "/live-editor/": "Live Editor",
    }

    for path, title in expected.items():
        response = client.get(path)
        assert response.status_code == 200
        assert title in response.text
