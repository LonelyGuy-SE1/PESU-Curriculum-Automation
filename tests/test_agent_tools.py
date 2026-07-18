import pytest

from app.services.agent_tools import call_tool, list_tool_schemas


def tool_names():
    return {tool["function"]["name"] for tool in list_tool_schemas()}


def test_agent_tool_schemas_are_function_tools():
    tools = list_tool_schemas()

    assert tools
    assert all(tool["type"] == "function" for tool in tools)
    assert "get_current_course_json" in tool_names()
    assert "get_curriculum_json" in tool_names()
    assert "diff_course_json" in tool_names()
    assert "create_document_draft" in tool_names()
    assert "apply_course_draft" not in tool_names()
    # New granular course tools
    assert "get_course_codes" in tool_names()
    assert "get_course_syllabus" in tool_names()
    assert "get_course_textbooks" in tool_names()
    assert "get_course_deterministic" in tool_names()
    assert "get_course_lab" in tool_names()
    assert "categorize_elective" in tool_names()
    assert "get_course_fields" in tool_names()


def test_diff_tool_returns_syllabus_changes():
    result = call_tool(
        "diff_course_json",
        {
            "current": {"units": [{"title": "Unit 1", "content": "Stacks, Queues"}]},
            "proposed": {"units": [{"title": "Unit 1", "content": "Stacks, Graphs"}]},
        },
    )

    assert "graphs" in result["topics_added"]
    assert "queues" in result["topics_removed"]


def test_preview_url_tool():
    assert call_tool("get_preview_url", {"kind": "course", "id": 12}) == {"url": "/api/preview/course/12"}
    assert call_tool("get_preview_url", {"kind": "draft", "id": 3}) == {"url": "/api/agent/drafts/3/preview"}


def test_unknown_tool_fails():
    with pytest.raises(LookupError):
        call_tool("missing_tool", {})


def test_invalid_preview_kind_fails():
    with pytest.raises(ValueError):
        call_tool("get_preview_url", {"kind": "refined", "id": 1})


def test_granular_course_tools_require_refined_id():
    for tool in ["get_course_codes", "get_course_syllabus", "get_course_textbooks",
                  "get_course_deterministic", "get_course_lab"]:
        with pytest.raises(ValueError, match="refined_id is required"):
            call_tool(tool, {})


def test_categorize_elective_requires_refined_id():
    with pytest.raises(ValueError, match="refined_id is required"):
        call_tool("categorize_elective", {})


def test_get_course_fields_requires_fields_array():
    with pytest.raises(ValueError, match="fields must be a non-empty array"):
        call_tool("get_course_fields", {"refined_id": 1})
    with pytest.raises(ValueError, match="fields must be a non-empty array"):
        call_tool("get_course_fields", {"refined_id": 1, "fields": []})
    with pytest.raises(ValueError, match="fields must be a non-empty array"):
        call_tool("get_course_fields", {"refined_id": 1, "fields": "not_an_array"})


def test_signal_done_requires_summary():
    with pytest.raises(ValueError, match="summary is required"):
        call_tool("signal_done", {})
    with pytest.raises(ValueError, match="summary is required"):
        call_tool("signal_done", {"summary": ""})


def test_create_curriculum_version_requires_name():
    with pytest.raises(ValueError, match="name is required"):
        call_tool("create_curriculum_version", {})
    with pytest.raises(ValueError, match="name is required"):
        call_tool("create_curriculum_version", {"name": ""})
