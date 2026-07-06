from app.preview import build_course_preview


def test_preview_uses_submission_deterministic_fields():
    row = {
        "course_title": "Data Structures",
        "semester": 3,
        "program": "wrong",
        "course_type": "wrong",
        "lecture_hours": 0,
        "_submission": {"credit_category": "5", "target_department": "CSE"},
    }

    course = build_course_preview(row)

    assert course["program"] == "B. TECH"
    assert course["lecture_hours"] == "4"
    assert course["practical_hours"] == "2"
    assert course["credits"] == "5"
    assert course["course_type"] == "Core Course-Lab Integrated"


def test_preview_suppresses_labs_for_theory_course():
    row = {
        "course_title": "Theory",
        "lab_experiments": ["Lab that should not render"],
        "_submission": {"credit_category": "4", "target_department": "CSE"},
    }

    course = build_course_preview(row)

    assert course["lab_experiments"] == []


def test_preview_parses_numbered_books():
    row = {
        "course_title": "Books",
        "text_books": ["1. First Book, 2024. 2. Second Book, 2025."],
        "_submission": {"credit_category": "4", "target_department": "CSE"},
    }

    course = build_course_preview(row)

    assert course["text_books"] == ["First Book, 2024.", "Second Book, 2025."]


def test_preview_cleans_reference_book_table_noise():
    row = {
        "course_title": "Books",
        "reference_books": """
Reference             1. First Reference, 2024.
Book(s):              2. Second Reference, 2025.
Course
Outcome               should not render
""",
        "_submission": {"credit_category": "4", "target_department": "CSE"},
    }

    course = build_course_preview(row)

    assert course["reference_books"] == ["First Reference, 2024.", "Second Reference, 2025."]
