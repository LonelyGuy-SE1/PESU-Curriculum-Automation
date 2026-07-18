import pytest

from app.services.deterministic import (
    _COURSE_TYPE_MAP,
    _HOURS_MAP,
    _PROGRAM_MAP,
    compute_course_type,
    compute_hours,
    compute_program,
)


# ---------------------------------------------------------------------------
# All valid categories
# ---------------------------------------------------------------------------

def test_hours_all_valid_categories():
    assert compute_hours("5") == {"lecture_hours": 4, "tutorial_hours": 0, "practical_hours": 2, "self_study": 5, "credits": 5}
    assert compute_hours("4") == {"lecture_hours": 4, "tutorial_hours": 0, "practical_hours": 0, "self_study": 4, "credits": 4}
    assert compute_hours("2") == {"lecture_hours": 2, "tutorial_hours": 0, "practical_hours": 0, "self_study": 2, "credits": 2}
    assert compute_hours("0") == {"lecture_hours": 0, "tutorial_hours": 0, "practical_hours": 0, "self_study": 0, "credits": 0}


def test_program_all_valid_departments():
    for dept in ("CSE", "AIML", "ECE", "ME", "EEE", "BT"):
        assert compute_program(dept) == "B. TECH"


def test_course_type_all_valid_categories():
    assert compute_course_type("0") == "Foundation Course"
    assert compute_course_type("5") == "Core Course-Lab Integrated"
    assert compute_course_type("4") == "Core Course"
    assert compute_course_type("2") == "Core Theory"


# ---------------------------------------------------------------------------
# Invalid inputs raise ValueError with descriptive message
# ---------------------------------------------------------------------------

def test_hours_invalid_raises_value_error():
    with pytest.raises(ValueError, match="Unknown credit_category"):
        compute_hours("9")


def test_hours_empty_string_raises_value_error():
    with pytest.raises(ValueError, match="Unknown credit_category"):
        compute_hours("")


def test_hours_none_raises_value_error():
    with pytest.raises((ValueError, TypeError)):
        compute_hours(None)


def test_program_invalid_raises_value_error():
    with pytest.raises(ValueError, match="Unknown department"):
        compute_program("XYZ")


def test_program_empty_raises_value_error():
    with pytest.raises(ValueError, match="Unknown department"):
        compute_program("")


def test_course_type_invalid_raises_value_error():
    with pytest.raises(ValueError, match="Unknown credit_category"):
        compute_course_type("9")


def test_course_type_empty_raises_value_error():
    with pytest.raises(ValueError, match="Unknown credit_category"):
        compute_course_type("")


# ---------------------------------------------------------------------------
# Error messages contain expected valid values
# ---------------------------------------------------------------------------

def test_hours_error_lists_valid_values():
    with pytest.raises(ValueError, match=str(sorted(_HOURS_MAP))):
        compute_hours("X")


def test_program_error_lists_valid_values():
    with pytest.raises(ValueError, match=str(sorted(_PROGRAM_MAP))):
        compute_program("X")


def test_course_type_error_lists_valid_values():
    with pytest.raises(ValueError, match=str(sorted(_COURSE_TYPE_MAP))):
        compute_course_type("X")


# ---------------------------------------------------------------------------
# Hours dict structure
# ---------------------------------------------------------------------------

def test_hours_dict_has_exact_keys():
    for cat in ("5", "4", "2", "0"):
        result = compute_hours(cat)
        assert set(result.keys()) == {"lecture_hours", "tutorial_hours", "practical_hours", "self_study", "credits"}


def test_credits_equals_category_for_valid():
    for cat, expected_credits in [("5", 5), ("4", 4), ("2", 2), ("0", 0)]:
        assert compute_hours(cat)["credits"] == expected_credits
