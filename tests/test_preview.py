from app.preview import build_course_preview
from app.rendering import templates
from app.services.curriculum import ordered_courses


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


def _course(**values):
    course = {
        "course_code": "",
        "course_title": "",
        "program": "B. TECH",
        "lecture_hours": "4",
        "tutorial_hours": "0",
        "practical_hours": "0",
        "self_study": "4",
        "credits": "4",
        "semester": "5",
        "course_type": "Core Course",
        "tools_languages": "",
        "desirable_knowledge": "",
        "prelude": "",
        "objectives": [],
        "course_outcomes": [],
        "units": [],
        "lab_experiments": [],
        "text_books": [],
        "reference_books": [],
    }
    course.update(values)
    return course


def test_curriculum_template_renders_regular_semester_summary():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(course_code="UE25CS251A", course_title="Digital Design", semester="3", credits="5", lecture_hours="4", practical_hours="2", self_study="5"),
            _course(course_code="UE25MA201A", course_title="Bridge Course", semester="3", credits="0", lecture_hours="2", self_study="0", course_type="Foundation Course"),
        ],
        semester=3,
        curriculum_year="2025-2026",
        asset_root="",
        show_summaries=True,
    )

    assert "III SEMESTER (2024-28 BATCH)" in html
    assert "UE24CS251A" in html
    assert "Digital Design" in html
    assert "Bridge Course" in html
    assert "4/6" in html


def test_curriculum_template_renders_semester_five_elective_summary():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(course_code="UE23CS351A", course_title="Database Management System", semester="5", lecture_hours="4", practical_hours="2", self_study="5", credits="5", course_type="Core Course-Lab Integrated"),
            _course(course_code="UE23CS342AAX", course_title="Elective I", semester="5", course_type="Elective Course"),
            _course(course_code="UE23CS342AA1", course_title="Advanced Algorithms", semester="5", course_type="Elective Course", tools_languages="C++"),
            _course(course_code="UE23CS343AB1", course_title="Image Processing", semester="5", course_type="Elective Course", tools_languages="Python"),
        ],
        semester=5,
        curriculum_year="2025-2026",
        asset_root="",
        show_summaries=True,
    )

    assert "V SEMESTER (2023-27 BATCH)" in html
    assert "Elective-I" in html
    assert "Elective-II" in html
    assert "Elective I" in html
    assert "Advanced Algorithms" in html
    assert "Image Processing" in html
    assert "ELECTIVES TO BE OPTED FOR SPECIALIZATION" in html
    assert "System and Core Computing (SCC)" in html
    assert "UE23CS342AA1" in html


def test_curriculum_template_renders_semester_six_elective_groups():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(course_code="UE23CS351B", course_title="Cloud Computing", semester="6", practical_hours="2", self_study="5", credits="5", course_type="Core Course-Lab Integrated"),
            _course(course_code="UE23CS342BAX", course_title="Elective III", semester="6", course_type="Elective Course"),
            _course(course_code="UE23CS343BBX", course_title="Elective IV", semester="6", course_type="Elective Course"),
            _course(course_code="UE23CS342BA1", course_title="Supply Chain Management for Engineers", semester="6", course_type="Elective Course"),
            _course(course_code="UE23CS343BB1", course_title="Heterogeneous Parallelism", semester="6", course_type="Elective Course"),
        ],
        semester=6,
        curriculum_year="2025-2026",
        asset_root="",
        show_summaries=True,
    )

    assert "VI SEMESTER (2023-27 BATCH)" in html
    assert "Elective-III" in html
    assert "Elective-IV" in html
    assert "ELECTIVES TO BE OPTED FOR SPECIALIZATION" in html
    assert "UE23CS343BB12" in html


def test_curriculum_template_renders_final_year_summary():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(course_code="UE22CS441A", course_title="Capstone Project Phase-III", semester="7", lecture_hours="0", practical_hours="16", self_study="4", credits="4", course_type="Project Work"),
            _course(course_code="UZ22UZ422A", course_title="Technical writing", semester="7", lecture_hours="0", tutorial_hours="2", self_study="2", credits="2", course_type="Special Topic"),
            _course(course_code="UE22AM421AXX", course_title="Special Topic", semester="7", lecture_hours="0", tutorial_hours="2", self_study="2", credits="2", course_type="Special Topic"),
            _course(course_code="UE22CS421B", course_title="Capstone Project Phase-IV", semester="8", lecture_hours="0", practical_hours="8", self_study="4", credits="4", course_type="Project Work"),
            _course(course_code="UE22CS461XB", course_title="Internship", semester="8", lecture_hours="0", practical_hours="16", self_study="8", credits="8", course_type="Internship"),
        ],
        semester="",
        curriculum_year="2025-2026",
        asset_root="",
        show_summaries=True,
    )

    assert "VII SEMESTER (2022-26 BATCH)" in html
    assert "VIII SEMESTER (2022-26 BATCH)" in html
    assert "Technical writing" in html
    assert "Internship" in html
    assert "AI Tools / Tools / Languages" not in html.split("VII SEMESTER", 1)[1].split("</article>", 1)[0]


def test_ordered_courses_preserves_refined_order_within_semester():
    rows = [
        {"id": 6, "semester": 5, "course_code": "UE23CS320A", "course_title": "Capstone Project", "credits": 2},
        {"id": 1, "semester": 5, "course_code": "UE23CS351A", "course_title": "Database Management System", "credits": 5},
    ]

    courses = ordered_courses(rows)

    assert [course["course_title"] for course in courses] == ["Database Management System", "Capstone Project"]
