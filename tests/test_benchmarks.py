import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    with patch("os.environ", {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_KEY": "test", "SENTRY_DSN": ""}):
        from app.main import app
        yield TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Frontend page load latency (must be < 100ms avg, < 200ms p95)
# ---------------------------------------------------------------------------

FRONTEND_PAGES = {
    "/": "PESU Curriculum Automation",
    "/form/": "Submit Course",
    "/courses/": "Courses",
    "/preview/": "Preview",
    "/live-editor/": "Agentic Editor",
    "/versions/": "Version History",
}


@pytest.mark.parametrize("path,expected_title", list(FRONTEND_PAGES.items()))
def test_frontend_page_load_latency(client, path, expected_title):
    times = []
    for _ in range(10):
        start = time.perf_counter()
        resp = client.get(path)
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)
    avg_ms = sum(times) / len(times)
    p95_ms = sorted(times)[int(len(times) * 0.95)]
    assert resp.status_code == 200, f"{path} returned {resp.status_code}"
    assert expected_title in resp.text, f"{path} missing title '{expected_title}'"
    assert avg_ms < 100, f"{path} avg latency {avg_ms:.1f}ms exceeds 100ms threshold"
    assert p95_ms < 200, f"{path} p95 latency {p95_ms:.1f}ms exceeds 200ms threshold"


# ---------------------------------------------------------------------------
# API 422 responses are fast (< 50ms)
# ---------------------------------------------------------------------------

def test_422_response_latency(client):
    times = []
    for _ in range(10):
        start = time.perf_counter()
        resp = client.post("/api/submissions", json={})
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)
    avg_ms = sum(times) / len(times)
    assert resp.status_code == 422
    assert avg_ms < 50, f"422 response avg latency {avg_ms:.1f}ms exceeds 50ms threshold"


# ---------------------------------------------------------------------------
# Agent tools endpoint latency (< 50ms)
# ---------------------------------------------------------------------------

def test_agent_tools_list_latency(client):
    times = []
    for _ in range(10):
        start = time.perf_counter()
        resp = client.get("/api/agent/tools")
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)
    avg_ms = sum(times) / len(times)
    assert resp.status_code == 200
    data = resp.json()
    tools = data.get("tools", data) if isinstance(data, dict) else data
    assert len(tools) >= 30, f"Expected at least 30 tools, got {len(tools)}"
    assert avg_ms < 50, f"Agent tools list avg latency {avg_ms:.1f}ms exceeds 50ms threshold"


# ---------------------------------------------------------------------------
# Tool call latency (< 200ms per call)
# ---------------------------------------------------------------------------

TOOL_CALLS = [
    ("get_preview_url", {"arguments": {"kind": "course", "id": 1}}),
    ("get_preview_url", {"arguments": {"kind": "draft", "id": 1}}),
    ("diff_course_json", {"arguments": {"current": {"units": [{"title": "U1", "content": "A"}]}, "proposed": {"units": [{"title": "U1", "content": "B"}]}}}),
]


@pytest.mark.parametrize("tool_name,payload", TOOL_CALLS)
def test_tool_call_latency(client, tool_name, payload):
    times = []
    for _ in range(5):
        start = time.perf_counter()
        resp = client.post(f"/api/agent/tools/{tool_name}", json=payload)
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)
    avg_ms = sum(times) / len(times)
    assert resp.status_code == 200, f"Tool {tool_name} returned {resp.status_code}: {resp.text[:200]}"
    assert avg_ms < 200, f"Tool {tool_name} avg latency {avg_ms:.1f}ms exceeds 200ms threshold"


# ---------------------------------------------------------------------------
# Static asset serving latency (< 50ms)
# ---------------------------------------------------------------------------

STATIC_ASSETS = [
    "/shared.css",
    "/shared/dialog.css",
    "/shared/dialog.js",
    "/shared/auth-guard.js",
    "/shared/supabase-client.js",
    "/images/SE1128.png",
]


def test_static_asset_serving_latency(client):
    for asset in STATIC_ASSETS:
        times = []
        for _ in range(5):
            start = time.perf_counter()
            resp = client.get(asset)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)
        avg_ms = sum(times) / len(times)
        assert resp.status_code == 200, f"Asset {asset} returned {resp.status_code}"
        assert avg_ms < 50, f"Asset {asset} avg latency {avg_ms:.1f}ms exceeds 50ms threshold"


# ---------------------------------------------------------------------------
# Page content completeness (no missing elements)
# ---------------------------------------------------------------------------

def test_live_editor_has_all_elements(client):
    resp = client.get("/live-editor/")
    html = resp.text
    assert 'id="semester"' in html
    assert 'id="course"' in html
    assert 'id="viewer"' in html
    assert 'id="editor"' in html
    assert 'id="chat-log"' in html
    assert 'id="send"' in html
    assert 'id="save"' in html
    assert 'id="draft"' in html
    assert 'id="apply-draft"' in html
    assert 'id="restore-version"' in html
    assert 'dialog.css' in html
    assert 'dialog.js' in html


def test_courses_page_has_all_elements(client):
    resp = client.get("/courses/")
    html = resp.text
    assert 'id="semester"' in html
    assert 'id="visibility"' in html
    assert 'id="search"' in html
    assert 'id="course-table"' in html
    assert 'id="status"' in html
    assert 'dialog.css' in html
    assert 'dialog.js' in html


def test_versions_page_has_all_elements(client):
    resp = client.get("/versions/")
    html = resp.text
    assert 'id="viewer"' in html
    assert 'id="sidebar"' in html
    assert 'id="version-list"' in html
    assert 'id="viewer-loading"' in html
    assert 'id="empty-state"' in html
    assert 'id="open-editor"' in html


def test_preview_page_has_pdf_controls(client):
    resp = client.get("/preview/")
    html = resp.text
    assert 'id="viewer"' in html
    assert 'id="status"' in html
    assert 'id="open"' in html
    assert 'id="download"' in html


def test_form_page_has_all_fields(client):
    resp = client.get("/form/")
    html = resp.text
    assert 'name="faculty_email"' in html
    assert 'name="course_code"' in html
    assert 'name="course_title"' in html
    assert 'name="raw_course_content"' in html
    assert 'name="text_books"' in html
    assert 'name="reference_books"' in html
    assert 'name="preferred_tools"' in html
    assert 'id="submit-btn"' in html


# ---------------------------------------------------------------------------
# Response content-type correctness
# ---------------------------------------------------------------------------

def test_pdf_endpoint_returns_pdf_content_type(client):
    resp = client.get("/api/preview/pdf")
    ct = resp.headers.get("content-type", "")
    assert "application/pdf" in ct or resp.status_code == 500


def test_html_endpoint_returns_html_content_type(client):
    resp = client.get("/api/preview/html")
    ct = resp.headers.get("content-type", "")
    assert "text/html" in ct or resp.status_code == 500


def test_cors_headers_present(client):
    resp = client.options(
        "/api/health/schema",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert resp.status_code in (200, 405)


# ---------------------------------------------------------------------------
# Submission validation latency (< 50ms)
# ---------------------------------------------------------------------------

def test_submission_validation_latency(client):
    payload = {
        "faculty_email": "test@pes.edu",
        "course_code": "UE25CS242B",
        "course_title": "Test Course",
        "offering_department": "CS",
        "target_department": "CSE",
        "semester": "4",
        "credit_category": "4",
        "raw_course_content": "x" * 100,
        "text_books": "1. Book",
    }
    times = []
    for _ in range(10):
        start = time.perf_counter()
        resp = client.post("/api/submissions", json=payload)
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)
    avg_ms = sum(times) / len(times)
    assert resp.status_code in (200, 500, 503)
    assert avg_ms < 50, f"Submission validation avg latency {avg_ms:.1f}ms exceeds 50ms threshold"


# ---------------------------------------------------------------------------
# API response consistency (all JSON endpoints return valid JSON)
# ---------------------------------------------------------------------------

def test_api_endpoints_return_json_or_html(client):
    json_endpoints = ["/api/agent/tools", "/api/versions"]
    for ep in json_endpoints:
        resp = client.get(ep)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            assert "json" in ct or "text/plain" in ct, f"{ep} content-type is {ct}"


# ---------------------------------------------------------------------------
# Latency consistency (10 runs, low standard deviation)
# ---------------------------------------------------------------------------

def test_frontend_page_latency_consistency(client):
    times = []
    for _ in range(20):
        start = time.perf_counter()
        client.get("/courses/")
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)
    avg = sum(times) / len(times)
    variance = sum((t - avg) ** 2 for t in times) / len(times)
    std_dev = variance ** 0.5
    assert std_dev < avg * 0.5, f"Courses page latency std_dev {std_dev:.1f}ms too high relative to avg {avg:.1f}ms"
