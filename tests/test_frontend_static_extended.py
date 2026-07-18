from pathlib import Path

import pytest

from fastapi.testclient import TestClient


LIVE_EDITOR_HTML = Path("frontend/live-editor/index.html")
COURSES_HTML = Path("frontend/courses/index.html")
SHARED_CSS = Path("frontend/shared.css")
DIALOG_CSS = Path("frontend/shared/dialog.css")
DIALOG_JS = Path("frontend/shared/dialog.js")


# ---------------------------------------------------------------------------
# Shared scrollbar CSS
# ---------------------------------------------------------------------------

def test_shared_css_has_scrollbar_rules():
    css = SHARED_CSS.read_text()
    assert "::-webkit-scrollbar" in css
    assert "scrollbar-width" in css
    assert "scrollbar-color" in css


def test_shared_css_scrollbar_uses_theme_variables():
    css = SHARED_CSS.read_text()
    assert "var(--border-strong)" in css
    assert "var(--muted)" in css


# ---------------------------------------------------------------------------
# Custom dialog
# ---------------------------------------------------------------------------

def test_dialog_css_exists():
    assert DIALOG_CSS.exists()


def test_dialog_js_exists():
    assert DIALOG_JS.exists()


def test_dialog_js_exposes_showConfirm():
    js = DIALOG_JS.read_text()
    assert "window.showConfirm" in js
    assert "new Promise" in js


def test_dialog_css_has_overlay_and_box():
    css = DIALOG_CSS.read_text()
    assert "dialog-overlay" in css
    assert "dialog-box" in css
    assert "dialog-actions" in css


def test_dialog_css_uses_theme_variables():
    css = DIALOG_CSS.read_text()
    assert "var(--background)" in css
    assert "var(--border)" in css
    assert "var(--radius)" in css
    assert "var(--foreground)" in css


# ---------------------------------------------------------------------------
# Live editor wires dialog
# ---------------------------------------------------------------------------

def test_live_editor_links_dialog_css():
    html = LIVE_EDITOR_HTML.read_text()
    assert 'dialog.css' in html


def test_live_editor_links_dialog_js():
    html = LIVE_EDITOR_HTML.read_text()
    assert 'dialog.js' in html


def test_live_editor_uses_show_confirm():
    js = Path("frontend/live-editor/live-editor.js").read_text()
    assert "showConfirm" in js
    assert js.count("showConfirm") >= 3


def test_live_editor_no_native_confirm():
    js = Path("frontend/live-editor/live-editor.js").read_text()
    assert "confirm(" not in js


# ---------------------------------------------------------------------------
# Courses page wires dialog
# ---------------------------------------------------------------------------

def test_courses_links_dialog_css():
    html = COURSES_HTML.read_text()
    assert 'dialog.css' in html


def test_courses_links_dialog_js():
    html = COURSES_HTML.read_text()
    assert 'dialog.js' in html


def test_courses_uses_show_confirm():
    js = Path("frontend/courses/courses.js").read_text()
    assert "showConfirm" in js


def test_courses_no_native_confirm():
    js = Path("frontend/courses/courses.js").read_text()
    assert "confirm(" not in js


# ---------------------------------------------------------------------------
# Frontend page imports shared.css (scrollbar applies everywhere)
# ---------------------------------------------------------------------------

def test_all_css_files_import_shared():
    css_files = [
        "frontend/courses/courses.css",
        "frontend/live-editor/live-editor.css",
        "frontend/versions/versions.css",
        "frontend/form/form.css",
        "frontend/preview/preview.css",
        "frontend/home/home.css",
    ]
    for path in css_files:
        text = Path(path).read_text()
        assert '@import "../shared.css"' in text, f"{path} missing shared.css import"


# ---------------------------------------------------------------------------
# Backend cache module structure
# ---------------------------------------------------------------------------

def test_cache_module_has_required_functions():
    import app.cache as c

    assert callable(c.get)
    assert callable(c.put)
    assert callable(c.invalidate)
    assert callable(c.close)
    assert callable(c._get_redis)


def test_cache_constants():
    import app.cache as c

    assert c.DEFAULT_TTL > 0
    assert c._MAX_MEMORY_ENTRIES > 0
    assert c._REDIS_RETRY_COOLDOWN > 0


# ---------------------------------------------------------------------------
# Deterministic module constants are accessible
# ---------------------------------------------------------------------------

def test_deterministic_maps_are_complete():
    from app.services.deterministic import _COURSE_TYPE_MAP, _HOURS_MAP, _PROGRAM_MAP

    assert set(_HOURS_MAP.keys()) == {"5", "4", "2", "0"}
    assert set(_COURSE_TYPE_MAP.keys()) == {"5", "4", "2", "0"}
    assert set(_PROGRAM_MAP.keys()) == {"CSE", "AIML", "ECE", "ME", "EEE", "BT"}


# ---------------------------------------------------------------------------
# Curriculum cache invalidation function signature
# ---------------------------------------------------------------------------

def test_invalidate_curriculum_cache_exists():
    from app.services.curriculum import invalidate_curriculum_cache
    assert callable(invalidate_curriculum_cache)


# ---------------------------------------------------------------------------
# Versions diff filtering
# ---------------------------------------------------------------------------

def test_versions_diff_imports_build_course_diff():
    from app.routes.versions import build_course_diff
    assert callable(build_course_diff)


def test_diffing_module_exports_shared_helpers():
    from app.services.diffing import diff_text_field, diff_list_field, diff_units_field, build_course_diff

    assert callable(diff_text_field)
    assert callable(diff_list_field)
    assert callable(diff_units_field)
    assert callable(build_course_diff)
