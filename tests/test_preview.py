from app.preview import build_course_preview
from app.rendering import templates
from app.services.curriculum import course_credits, ordered_courses


# ---------------------------------------------------------------------------
# _course helper
# ---------------------------------------------------------------------------

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
        "is_elective": False,
        "status": "refined",
        "render_detail": True,
        "refined_id": 1,
    }
    course.update(values)
    return course


# ---------------------------------------------------------------------------
# build_course_preview: deterministic fields
# ---------------------------------------------------------------------------

def test_preview_uses_submission_deterministic_fields():
    row = {
        "course_title": "Data Structures",
        "semester": 3,
        "program": "",
        "course_type": "",
        "lecture_hours": 0,
        "_submission": {"credit_category": "5", "target_department": "CSE"},
    }
    course = build_course_preview(row)

    assert course["program"] == "B. TECH"
    assert course["lecture_hours"] == "4"
    assert course["practical_hours"] == "2"
    assert course["credits"] == "5"
    assert course["course_type"] == "Core Course-Lab Integrated"


def test_preview_keeps_refined_source_values_when_present():
    row = {
        "course_title": "Internship",
        "semester": 8,
        "program": "B. TECH",
        "course_type": "Internship",
        "lecture_hours": 0,
        "tutorial_hours": 0,
        "practical_hours": 16,
        "self_study": 8,
        "credits": 8,
        "_submission": {"credit_category": "4", "target_department": "CSE"},
    }
    course = build_course_preview(row)

    assert course["practical_hours"] == "16"
    assert course["credits"] == "8"
    assert course["course_type"] == "Internship"


# ---------------------------------------------------------------------------
# build_course_preview: render_detail / has_content
# ---------------------------------------------------------------------------

def test_render_detail_false_when_no_content():
    row = {
        "course_title": "Empty Course",
        "semester": 3,
        "_submission": {"credit_category": "4", "target_department": "CSE"},
    }
    course = build_course_preview(row)
    assert course["render_detail"] is False


def test_render_detail_true_when_has_objectives():
    row = {
        "course_title": "Course With Content",
        "semester": 3,
        "objectives": ["Objective 1"],
        "_submission": {"credit_category": "4", "target_department": "CSE"},
    }
    course = build_course_preview(row)
    assert course["render_detail"] is True


def test_render_detail_true_when_has_text_books():
    row = {
        "course_title": "Course With Books",
        "semester": 3,
        "text_books": "1. Some Book",
        "_submission": {"credit_category": "4", "target_department": "CSE"},
    }
    course = build_course_preview(row)
    assert course["render_detail"] is True


def test_render_detail_true_when_has_units():
    row = {
        "course_title": "Course With Units",
        "semester": 3,
        "units": [{"title": "Unit 1", "content": "Content", "hours": 4}],
        "_submission": {"credit_category": "4", "target_department": "CSE"},
    }
    course = build_course_preview(row)
    assert course["render_detail"] is True


def test_render_detail_false_when_summary_only_even_with_content():
    row = {
        "course_title": "Hidden Course",
        "semester": 3,
        "status": "summary_only",
        "objectives": ["Objective 1"],
        "_submission": {"credit_category": "4", "target_department": "CSE"},
    }
    course = build_course_preview(row)
    assert course["render_detail"] is False


# ---------------------------------------------------------------------------
# build_course_preview: books / experiments
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# course_credits helper
# ---------------------------------------------------------------------------

def test_course_credits_reads_from_credits_column():
    assert course_credits({"credits": 5}) == 5


def test_course_credits_falls_back_to_submission_category():
    assert course_credits({"_submission": {"credit_category": "2"}}) == 2


def test_course_credits_returns_zero_for_empty_row():
    assert course_credits({}) == 0


def test_course_credits_prefers_credits_over_category():
    assert course_credits({"credits": 4, "_submission": {"credit_category": "2"}}) == 4


# ---------------------------------------------------------------------------
# ordered_courses: credit sort
# ---------------------------------------------------------------------------

def test_ordered_courses_sorts_by_credits_descending():
    rows = [
        {"id": 1, "semester": 3, "course_code": "UE99XX111A", "course_title": "Two Credit", "credits": 2},
        {"id": 2, "semester": 3, "course_code": "UE99XX222A", "course_title": "Five Credit", "credits": 5},
        {"id": 3, "semester": 3, "course_code": "UE99XX333A", "course_title": "Four Credit", "credits": 4},
    ]
    courses = ordered_courses(rows)
    assert [c["course_title"] for c in courses] == ["Five Credit", "Four Credit", "Two Credit"]


def test_ordered_courses_reads_credits_from_submission_category():
    rows = [
        {"id": 1, "semester": 4, "course_code": "UE99XX111A", "course_title": "Theory", "_submission": {"credit_category": "2"}},
        {"id": 2, "semester": 4, "course_code": "UE99XX222A", "course_title": "Lab Integrated", "_submission": {"credit_category": "5"}},
    ]
    courses = ordered_courses(rows)
    assert [c["course_title"] for c in courses] == ["Lab Integrated", "Theory"]


def test_ordered_courses_preserves_order_within_same_credits():
    rows = [
        {"id": 6, "semester": 5, "course_code": "UE23CS320A", "course_title": "Capstone Project", "credits": 2},
        {"id": 1, "semester": 5, "course_code": "UE23CS351A", "course_title": "Database Management System", "credits": 5},
    ]
    courses = ordered_courses(rows)
    assert [c["course_title"] for c in courses] == ["Database Management System", "Capstone Project"]


def test_ordered_courses_separates_semesters():
    rows = [
        {"id": 1, "semester": 3, "course_code": "UE99XX111A", "course_title": "Sem 3 Course", "credits": 4},
        {"id": 2, "semester": 1, "course_code": "UE99XX222A", "course_title": "Sem 1 Course", "credits": 5},
    ]
    courses = ordered_courses(rows)
    assert courses[0]["semester"] == "1"
    assert courses[1]["semester"] == "3"


# ---------------------------------------------------------------------------
# Template: semester summary tables
# ---------------------------------------------------------------------------

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


def test_curriculum_template_clubs_semester_one_and_two_summary():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(course_code="UE25CS151A", course_title="Python", semester="1", credits="5", practical_hours="2", self_study="5"),
            _course(course_code="UE25CS151B", course_title="C", semester="2", credits="5", practical_hours="2", self_study="5"),
        ],
        semester="",
        curriculum_year="2025-2026",
        asset_root="",
        show_summaries=True,
    )
    early = html.split("III SEMESTER", 1)[0]
    assert "I SEMESTER (2025-29 BATCH)" in early
    assert "II SEMESTER (2025-29 BATCH)" in early
    assert early.count('class="summary-page"') == 4


def test_curriculum_template_renders_final_year_summary():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(course_code="UE22CS441A", course_title="Capstone Project Phase-III", semester="7", lecture_hours="0", practical_hours="16", self_study="4", credits="4", course_type="Project Work"),
            _course(course_code="UZ22UZ422A", course_title="Technical writing", semester="7", lecture_hours="0", tutorial_hours="2", self_study="2", credits="2", course_type="Special Topic"),
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


def test_summary_only_courses_do_not_render_detail_pages():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(course_code="UZ24UZ221A", course_title="CIE L1", semester="3", credits="2", lecture_hours="2", self_study="2", course_type="Special Topic", status="summary_only", render_detail=False),
        ],
        semester=3,
        curriculum_year="2025-2026",
        asset_root="",
        show_summaries=True,
    )
    assert "CIE L1" in html
    assert "Course Objectives:" not in html


def test_empty_content_course_skips_detail_page():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(course_code="UE99XX111A", course_title="Bare Course", semester="3", credits="2", render_detail=False),
        ],
        semester=3,
        curriculum_year="2025-2026",
        asset_root="",
        show_summaries=True,
    )
    assert "Bare Course" in html
    assert "Course Objectives:" not in html


# ---------------------------------------------------------------------------
# Template: semester 5/6 elective summaries + placeholders
# ---------------------------------------------------------------------------

def test_curriculum_template_renders_semester_five_elective_summary():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(refined_id=1, course_code="UE23CS351A", course_title="Database Management System", semester="5", lecture_hours="4", practical_hours="2", self_study="5", credits="5", course_type="Core Course-Lab Integrated", is_elective=False),
            _course(refined_id=2, course_code="UE23CS342AAX", course_title="Elective I", semester="5", course_type="Elective Course", is_elective=True),
            _course(refined_id=3, course_code="UE23CS342AA1", course_title="Advanced Algorithms", semester="5", course_type="Elective Course", tools_languages="C++", is_elective=True),
            _course(refined_id=4, course_code="UE23CS343AB1", course_title="Image Processing", semester="5", course_type="Elective Course", tools_languages="Python", is_elective=True),
        ],
        semester=5,
        curriculum_year="2025-2026",
        asset_root="",
        show_summaries=True,
        specializations=[
            {"id": 1, "semester": 5, "letter": "A", "name": "System and Core Computing (SCC)", "key": "SCC", "academic_year": ""},
            {"id": 2, "semester": 5, "letter": "B", "name": "Machine Intelligence and Data Science (MIDS)", "key": "MIDS", "academic_year": ""},
            {"id": 3, "semester": 5, "letter": "C", "name": "Cyber Security and Connected Systems (CSCS)", "key": "CSCS", "academic_year": ""},
        ],
        specialization_assignments=[
            {"refined_id": 3, "specialization_id": 1},
        ],
    )
    assert "V SEMESTER (2023-27 BATCH)" in html
    assert "Elective-I" in html
    assert "Elective-II" in html
    assert "Advanced Algorithms" in html
    assert "Image Processing" in html
    assert "ELECTIVES TO BE OPTED FOR SPECIALIZATION" in html
    assert "System and Core Computing (SCC)" in html
    assert "UE23CS342AA1" in html


def test_curriculum_template_renders_semester_six_elective_groups():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(refined_id=1, course_code="UE23CS351B", course_title="Cloud Computing", semester="6", practical_hours="2", self_study="5", credits="5", course_type="Core Course-Lab Integrated", is_elective=False),
            _course(refined_id=2, course_code="UE23CS342BAX", course_title="Elective III", semester="6", course_type="Elective Course", is_elective=True),
            _course(refined_id=3, course_code="UE23CS343BBX", course_title="Elective IV", semester="6", course_type="Elective Course", is_elective=True),
            _course(refined_id=4, course_code="UE23CS342BA1", course_title="Supply Chain Management for Engineers", semester="6", course_type="Elective Course", is_elective=True),
            _course(refined_id=5, course_code="UE23CS343BB1", course_title="Heterogeneous Parallelism", semester="6", course_type="Elective Course", is_elective=True),
        ],
        semester=6,
        curriculum_year="2025-2026",
        asset_root="",
        show_summaries=True,
        specializations=[
            {"id": 1, "semester": 6, "letter": "A", "name": "System and Core Computing (SCC)", "key": "SCC", "academic_year": ""},
            {"id": 2, "semester": 6, "letter": "B", "name": "Machine Intelligence and Data Science (MIDS)", "key": "MIDS", "academic_year": ""},
            {"id": 3, "semester": 6, "letter": "C", "name": "Cyber Security and Connected Systems (CSCS)", "key": "CSCS", "academic_year": ""},
        ],
        specialization_assignments=[
            {"refined_id": 5, "specialization_id": 3},
        ],
    )
    assert "VI SEMESTER (2023-27 BATCH)" in html
    assert "Elective-III" in html
    assert "Elective-IV" in html
    assert "ELECTIVES TO BE OPTED FOR SPECIALIZATION" in html
    assert "UE23CS343BB1" in html


def test_sem5_core_table_excludes_electives_and_placeholders():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(refined_id=1, course_code="UE23CS351A", course_title="DBMS", semester="5", credits="4", is_elective=False),
            _course(refined_id=2, course_code="UE23CS342AAX", course_title="Elective I", semester="5", is_elective=True),
            _course(refined_id=3, course_code="UE23CS342AA1", course_title="Advanced Algorithms", semester="5", is_elective=True),
            _course(refined_id=4, course_code="UE23CS342AA2", course_title="Cloud Architecture", semester="5", is_elective=True),
        ],
        semester=5,
        curriculum_year="2025-2026",
        asset_root="",
        show_summaries=True,
    )
    core_section = html.split("Elective-I", 1)[0]
    assert "DBMS" in core_section
    assert "Advanced Algorithms" not in core_section
    assert "Cloud Architecture" not in core_section


def test_sem5_core_table_excludes_no_course_offered():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(refined_id=1, course_code="UE23CS351A", course_title="DBMS", semester="5", credits="4", is_elective=False),
            _course(refined_id=2, course_code="UE23CS999A", course_title="No Course Offered", semester="5", credits="0", is_elective=False, render_detail=False),
        ],
        semester=5,
        curriculum_year="2025-2026",
        asset_root="",
        show_summaries=True,
    )
    sem_section = html.split("V SEMESTER", 1)[1] if "V SEMESTER" in html else ""
    assert "DBMS" in sem_section
    assert "No Course Offered" not in sem_section


def test_sem5_summary_shows_placeholder_electives():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(refined_id=1, course_code="UE23CS351A", course_title="DBMS", semester="5", credits="4", is_elective=False),
            _course(refined_id=2, course_code="UE23CS342AA1", course_title="Advanced Algorithms", semester="5", credits="4", is_elective=True),
        ],
        semester=5,
        curriculum_year="2025-2026",
        asset_root="",
        show_summaries=True,
    )
    assert "Elective I" in html
    assert "Elective II" in html


def test_sem6_summary_shows_placeholder_electives():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(refined_id=1, course_code="UE23CS351B", course_title="Cloud Computing", semester="6", credits="4", is_elective=False),
            _course(refined_id=3, course_code="UE23CS343BB1", course_title="Heterogeneous Parallelism", semester="6", credits="4", is_elective=True),
        ],
        semester=6,
        curriculum_year="2025-2026",
        asset_root="",
        show_summaries=True,
    )
    assert "Elective III" in html
    assert "Elective IV" in html


def test_sem5_summary_total_includes_placeholder_credits():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(refined_id=1, course_code="UE23CS351A", course_title="DBMS", semester="5", credits="4", is_elective=False),
            _course(refined_id=2, course_code="UE23CS342AA1", course_title="Advanced Algorithms", semester="5", credits="4", is_elective=True),
        ],
        semester=5,
        curriculum_year="2025-2026",
        asset_root="",
        show_summaries=True,
    )
    sem5_section = html.split("V SEMESTER", 1)[1].split("</tbody>", 1)[0]
    assert ">12<" in sem5_section


def test_no_summary_page_for_empty_semester():
    html = templates.get_template("jinja_sample.html").render(
        courses=[
            _course(course_code="UE99XX111A", course_title="Sem 3 Only", semester="3", credits="4"),
        ],
        semester="",
        curriculum_year="2025-2026",
        asset_root="",
        show_summaries=True,
    )
    assert "V SEMESTER" not in html
    assert "VI SEMESTER" not in html
