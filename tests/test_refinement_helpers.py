from app.services.refinement import _books, _course_code, _prior_matches, _units_from_course_contents, build_refined_payload
from app.services.elective_categorization import is_elective_course


def test_elective_detection_mirrors_specialization_code_groups():
    assert is_elective_course({"semester": 5, "course_code": "UE23CS342AAX"})
    assert is_elective_course({"semester": 6, "course_code": "UE23CS343BBX"})
    assert not is_elective_course({"semester": 4, "course_code": "UE23CS342AAX"})
    assert not is_elective_course({"semester": 5, "course_code": "UE23CS351A"})


def test_units_are_read_from_course_contents():
    raw = """
Course Contents
Unit 1: Intro - A, B. 14 Hours
Unit 2: Core - C, D. 14 Hours
Unit 3: Advanced - E, F. 14 Hours
Unit 4: Applications - G, H. 14 Hours
Text Book(s):
1. Book
"""

    units = _units_from_course_contents(raw)

    assert [unit["title"] for unit in units] == ["Unit 1: Intro", "Unit 2: Core", "Unit 3: Advanced", "Unit 4: Applications"]
    assert units[0]["content"] == "A, B."


def test_books_remove_page_noise_and_numbering():
    books = _books("Text Book(s): 1. First Book, 2024.\nP.E.S. University\n2. Second Book, 2025.")

    assert books == ["First Book, 2024.", "Second Book, 2025."]


def test_books_stop_before_course_outcome_and_remove_split_labels():
    books = _books(
        """
Reference             1. "Digital Design & Computer Architecture", David Money Harris, Sarah L. Harris, 2nd
Book(s):              Edition, Elsevier, 2013.
                      2. "Computer Organization and Design", David A. Patterson, John L. Hennessey 5th Edition,
                      Elsevier, 2013.

Course                     • Perform analysis of digital logic circuits.
Outcome                    • Design control logic using finite state machines.
"""
    )

    assert books == [
        '"Digital Design & Computer Architecture", David Money Harris, Sarah L. Harris, 2nd Edition, Elsevier, 2013.',
        '"Computer Organization and Design", David A. Patterson, John L. Hennessey 5th Edition, Elsevier, 2013.',
    ]


def test_books_remove_inline_split_label():
    books = _books("1. TinyML Cookbook: Combine artificial intelligence and ultra- Book(s) low-power embedded devices, 2022.")

    assert books == ["TinyML Cookbook: Combine artificial intelligence and ultra-low-power embedded devices, 2022."]


def test_prior_matches_only_existing_courses():
    prior = [
        "UE24CS241B - Design and Analysis of Algorithms",
        "UE24CS252A - Data Structures and Applications",
        "UE24CS252B - Computer Networks",
    ]

    matched = _prior_matches("Design and Analysis of Algorithm, Data Structures & Its Applications, Machine Intelligence", prior)

    assert matched == "UE24CS241B - Design and Analysis of Algorithms, UE24CS252A - Data Structures and Applications"


def test_course_code_is_read_from_raw_content():
    assert _course_code("Course Code: UE23CS342BB12\nCourse Title: SOC") == "UE23CS342BB12"


def test_refined_payload_keeps_deterministic_fields_and_four_units():
    sub = {
        "id": 10,
        "semester": "3",
        "course_title": "data structures",
        "target_department": "CSE",
        "credit_category": "5",
        "raw_course_content": """
Course Code: UE24CS252A
Unit 1: Lists - linked lists. 14 Hours
Unit 2: Stacks - stacks. 14 Hours
Unit 3: Trees - trees. 14 Hours
Unit 4: Graphs - graphs. 14 Hours
""",
        "text_books": "1. Data Structures Book.",
        "reference_books": "",
        "preferred_tools": "C",
    }
    out = {
        "course_title": "Data Structures",
        "objectives": ["Use data structures"],
        "course_outcomes": ["Implement data structures"],
        "units": _units_from_course_contents(sub["raw_course_content"]),
        "tools_languages": "C",
    }

    payload = build_refined_payload(sub, out, [])

    assert payload["program"] == "B. TECH"
    assert payload["course_code"] == "UE24CS252A"
    assert payload["credits"] == 5
    assert payload["course_type"] == "Core Course-Lab Integrated"
    assert len(payload["units"]) == 4
    assert sum(unit["hours"] for unit in payload["units"]) == 56
