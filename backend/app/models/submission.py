
from pydantic import BaseModel, Field, field_validator


class ParsedCourseCode(BaseModel):
    year: str
    dept: str
    semester: str
    offering_dept: str
    target_dept: str
    credit_category: str
    is_lateral: bool
    base_code: str


def parse_course_code(code: str) -> ParsedCourseCode:
    """Parse PESU course code like UE25CS242B into components."""
    code = code.strip().upper().replace(" ", "")
    
    if not code.startswith("UE"):
        raise ValueError("Course code must start with 'UE'")
    
    # UE + year (2 digits) + dept (2 chars) + number (3 digits) + suffix
    # UE25CS242B -> year=25, dept=CS, num=242, suffix=B
    import re
    match = re.match(r"^UE(\d{2})([A-Z]{2})(\d{3})([A-Z\*]+)$", code)
    if not match:
        raise ValueError(f"Invalid course code format: {code}")
    
    year, dept, num_str, suffix = match.groups()
    num = int(num_str)

    # Number format: [semester_group][credits][sequence]
    # e.g. 151 -> group=1, credits=5, seq=1
    # e.g. 242 -> group=2, credits=4, seq=2
    semester_group = num // 100
    credits_digit = (num // 10) % 10
    credit_category = str(credits_digit) if credits_digit in (0, 2, 4, 5) else "4"

    # Semester: each group covers 2 semesters.
    # A/B suffix determines odd/even within the group.
    is_even = suffix.startswith("B") or suffix.endswith("B") or suffix in ("XX", "XB")
    semester = str(semester_group * 2 - 1 + (1 if is_even else 0))
    
    # Map department to offering_department
    dept_map = {
        "CS": "CS",
        "EC": "CS",
        "EE": "CS",
        "ME": "CS",
        "BT": "CS",
        "AI": "CS",
        "ML": "CS",
        "MA": "MA",
        "PH": "MA",
        "CH": "MA",
        "HU": "UZ",
        "UZ": "UZ",
    }
    offering_dept = dept_map.get(dept, "CS")
    
    # Target department is based on program (all map to CSE for CS dept courses)
    target_map = {
        "CS": "CSE",
        "EC": "ECE",
        "EE": "EEE",
        "ME": "ME",
        "BT": "BT",
        "AI": "AIML",
        "ML": "AIML",
    }
    target_dept = target_map.get(dept, "CSE")
    
    is_lateral = "*" in suffix
    
    return ParsedCourseCode(
        year=year,
        dept=dept,
        semester=semester,
        offering_dept=offering_dept,
        target_dept=target_dept,
        credit_category=credit_category,
        is_lateral=is_lateral,
        base_code=code,
    )


class CourseSubmission(BaseModel):
    faculty_email: str = Field(default="", max_length=254)
    course_title: str = Field(min_length=3, max_length=150)
    course_code: str = Field(min_length=8, max_length=12)  # e.g., UE25CS242B
    raw_course_content: str = Field(min_length=50)
    text_books: str = Field(min_length=5)
    reference_books: str = ""
    preferred_tools: str = ""
    credit_category: str = ""

    @field_validator("faculty_email", "course_title", "course_code", "raw_course_content", "text_books", "reference_books", "preferred_tools", "credit_category", mode="before")
    @classmethod
    def strip(cls, value):
        return value.strip() if isinstance(value, str) else value
