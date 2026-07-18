import pytest

from app.services.deterministic import compute_course_type, compute_hours, compute_program


def test_credit_category_hours():
    assert compute_hours("5") == {"lecture_hours": 4, "tutorial_hours": 0, "practical_hours": 2, "self_study": 5, "credits": 5}
    assert compute_hours("0") == {"lecture_hours": 0, "tutorial_hours": 0, "practical_hours": 0, "self_study": 0, "credits": 0}


def test_program_mapping():
    assert compute_program("CSE") == "B. TECH"
    assert compute_program("AIML") == "B. TECH"


def test_course_type_mapping():
    assert compute_course_type("5") == "Core Course-Lab Integrated"
    assert compute_course_type("2") == "Core Theory"


def test_unknown_values_fail_fast():
    with pytest.raises(ValueError):
        compute_hours("9")
    with pytest.raises(ValueError):
        compute_program("XX")
    with pytest.raises(ValueError):
        compute_course_type("9")
