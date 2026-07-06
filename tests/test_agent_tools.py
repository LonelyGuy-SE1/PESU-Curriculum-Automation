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
