"""Tests for the elective categorization pipeline."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.elective_categorization import (
    _confirmation,
    _course_content,
    _parse_llm_response,
    _persist_assignments,
    _validate_assignments,
    categorize_refined_elective,
    is_elective_course,
)


# --- is_elective_course ---


def test_elective_course_semester_5_with_marker():
    assert is_elective_course({"semester": 5, "course_code": "UE23CS342AAX"})


def test_elective_course_semester_6_with_marker():
    assert is_elective_course({"semester": 6, "course_code": "UE23CS343BBX"})


def test_not_elective_wrong_semester():
    assert not is_elective_course({"semester": 4, "course_code": "UE23CS342AAX"})


def test_not_elective_no_marker():
    assert not is_elective_course({"semester": 5, "course_code": "UE23CS351A"})


def test_not_elective_missing_code():
    assert not is_elective_course({"semester": 5})


def test_not_elective_missing_semester():
    assert not is_elective_course({"course_code": "UE23CS342AAX"})


# --- _course_content ---


def test_course_content_extracts_units():
    course = {
        "course_title": "Data Structures",
        "units": [
            {"title": "Unit 1", "content": "Arrays, Linked Lists"},
            {"title": "Unit 2", "content": "Trees, Graphs"},
        ],
    }
    result = _course_content(course)
    assert "Data Structures" in result
    assert "Unit 1: Arrays, Linked Lists" in result
    assert "Unit 2: Trees, Graphs" in result


def test_course_content_handles_non_dict_units():
    course = {"units": ["Unit 1 content", "Unit 2 content"]}
    result = _course_content(course)
    assert "Unit 1 content" in result


def test_course_content_truncates_at_18000():
    course = {"course_title": "X", "objectives": "A" * 20000}
    result = _course_content(course)
    assert len(result) <= 18000


def test_course_content_empty():
    assert _course_content({}) == ""


# --- _confirmation ---


def test_confirmation_structure():
    result = _confirmation("some_reason", refined_id=1)
    assert result["assigned"] is False
    assert result["needs_human_confirmation"] is True
    assert result["reason"] == "some_reason"
    assert result["refined_id"] == 1


def test_confirmation_no_extra():
    result = _confirmation("test")
    assert len(result) == 3


# --- _parse_llm_response ---


def test_parse_llm_response_valid():
    resp = {"confidence": 0.9, "assignments": [{"specialization_id": 1, "confidence": 0.85, "reasoning": "OK"}]}
    conf, assignments = _parse_llm_response(resp)
    assert conf == 0.9
    assert len(assignments) == 1


def test_parse_llm_response_not_dict():
    assert _parse_llm_response("bad") is None


def test_parse_llm_response_missing_confidence():
    assert _parse_llm_response({"assignments": []}) is None


def test_parse_llm_response_bad_confidence():
    assert _parse_llm_response({"confidence": "abc", "assignments": []}) is None


def test_parse_llm_response_no_assignments():
    assert _parse_llm_response({"confidence": 0.9}) is None


def test_parse_llm_response_empty_assignments():
    assert _parse_llm_response({"confidence": 0.9, "assignments": []}) is None


# --- _validate_assignments ---


def test_validate_assignments_valid():
    result = _validate_assignments(
        [{"specialization_id": 1, "confidence": 0.9, "reasoning": "Fits well"}],
        {1, 2},
    )
    assert result is None


def test_validate_assignments_invalid_id():
    result = _validate_assignments(
        [{"specialization_id": 99, "confidence": 0.9, "reasoning": "X"}],
        {1, 2},
    )
    assert result["reason"] == "unknown_specialization_id"


def test_validate_assignments_low_confidence():
    result = _validate_assignments(
        [{"specialization_id": 1, "confidence": 0.5, "reasoning": "X"}],
        {1},
    )
    assert result["reason"] == "low_assignment_confidence"


def test_validate_assignments_empty_reasoning():
    result = _validate_assignments(
        [{"specialization_id": 1, "confidence": 0.9, "reasoning": "  "}],
        {1},
    )
    assert result["reason"] == "low_assignment_confidence"


def test_validate_assignments_bad_format():
    result = _validate_assignments([{"bad": "data"}], {1})
    assert result["reason"] == "invalid_model_assignment"


# --- _persist_assignments ---


@patch("app.services.elective_categorization.supabase")
def test_persist_assignments_inserts(mock_supabase):
    table_mock = MagicMock()
    mock_supabase.table.return_value = table_mock
    table_mock.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

    created = _persist_assignments(10, [{"specialization_id": 1, "confidence": 0.9, "reasoning": "OK"}])
    assert created == 1
    table_mock.insert.assert_called_once()


@patch("app.services.elective_categorization.supabase")
def test_persist_assignments_skips_existing(mock_supabase):
    table_mock = MagicMock()
    mock_supabase.table.return_value = table_mock
    table_mock.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{"id": 1}]

    created = _persist_assignments(10, [{"specialization_id": 1, "confidence": 0.9, "reasoning": "OK"}])
    assert created == 0
    table_mock.insert.assert_not_called()


# --- categorize_refined_elective (integration with mocks) ---


@patch("app.services.elective_categorization.first_row", return_value=None)
def test_categorize_not_found(_mock_first_row):
    with pytest.raises(LookupError, match="not found"):
        categorize_refined_elective(999)


@patch("app.services.elective_categorization.first_row")
def test_categorize_not_an_elective(mock_first_row):
    mock_first_row.return_value = {"id": 1, "is_elective": False, "semester": 3, "course_code": "UE23CS101"}
    result = categorize_refined_elective(1)
    assert result["assigned"] is False
    assert result["reason"] == "not_an_elective"


@patch("app.services.elective_categorization.first_row")
@patch("app.services.elective_categorization._fetch_tracks", return_value=[])
def test_categorize_no_tracks_for_semester(_mock_tracks, mock_first_row):
    mock_first_row.return_value = {"id": 1, "is_elective": True, "semester": 5, "course_code": "UE23CS342AA"}
    result = categorize_refined_elective(1)
    assert result["reason"] == "no_specializations_for_semester"


@patch("app.services.elective_categorization.llm", side_effect=RuntimeError("timeout"))
@patch("app.services.elective_categorization._fetch_tracks")
@patch("app.services.elective_categorization.first_row")
def test_categorize_model_error(mock_first_row, mock_tracks, _mock_llm):
    mock_first_row.return_value = {"id": 1, "is_elective": True, "semester": 5, "course_code": "UE23CS342AA", "course_title": "X"}
    mock_tracks.return_value = [{"id": 10, "semester": 5}]
    result = categorize_refined_elective(1)
    assert result["reason"] == "model_error"


@patch("app.services.elective_categorization.llm")
@patch("app.services.elective_categorization._fetch_tracks")
@patch("app.services.elective_categorization.first_row")
def test_categorize_low_confidence(mock_first_row, mock_tracks, mock_llm):
    mock_first_row.return_value = {"id": 1, "is_elective": True, "semester": 5, "course_code": "UE23CS342AA", "course_title": "X"}
    mock_tracks.return_value = [{"id": 10, "semester": 5, "letter": "A", "name": "AI"}]
    mock_llm.return_value = {"confidence": 0.5, "assignments": [{"specialization_id": 10, "confidence": 0.9, "reasoning": "Maybe"}]}
    result = categorize_refined_elective(1)
    assert result["reason"] == "low_confidence_or_no_match"


@patch("app.services.elective_categorization.llm")
@patch("app.services.elective_categorization._fetch_tracks")
@patch("app.services.elective_categorization.first_row")
def test_categorize_unknown_specialization_id(mock_first_row, mock_tracks, mock_llm):
    mock_first_row.return_value = {"id": 1, "is_elective": True, "semester": 5, "course_code": "UE23CS342AA", "course_title": "X"}
    mock_tracks.return_value = [{"id": 10, "semester": 5, "letter": "A", "name": "AI"}]
    mock_llm.return_value = {
        "confidence": 0.95,
        "assignments": [{"specialization_id": 999, "confidence": 0.9, "reasoning": "Maybe"}],
    }
    result = categorize_refined_elective(1)
    assert result["reason"] == "unknown_specialization_id"


@patch("app.services.elective_categorization._persist_assignments", return_value=1)
@patch("app.services.elective_categorization._validate_assignments", return_value=None)
@patch("app.services.elective_categorization._parse_llm_response")
@patch("app.services.elective_categorization.llm")
@patch("app.services.elective_categorization._fetch_tracks")
@patch("app.services.elective_categorization.first_row")
def test_categorize_happy_path(mock_first_row, mock_tracks, mock_llm, mock_parse, mock_validate, mock_persist):
    mock_first_row.return_value = {"id": 1, "is_elective": True, "semester": 5, "course_code": "UE23CS342AA", "course_title": "ML"}
    mock_tracks.return_value = [{"id": 10, "semester": 5, "letter": "A", "name": "AI"}]
    mock_llm.return_value = {}
    mock_parse.return_value = (0.95, [{"specialization_id": 10, "confidence": 0.92, "reasoning": "Fits AI track"}])

    result = categorize_refined_elective(1)
    assert result["assigned"] is True
    assert result["assignments_created"] == 1
    assert result["assignments"][0]["specialization_id"] == 10
    mock_persist.assert_called_once_with(1, [{"specialization_id": 10, "confidence": 0.92, "reasoning": "Fits AI track"}])
