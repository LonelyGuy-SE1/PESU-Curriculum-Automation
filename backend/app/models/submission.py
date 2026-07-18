
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
    
    # Extract semester from number (hundreds digit)
    semester_digit = num // 100
    base_sem = semester_digit
    
    # Determine if even semester from suffix
    # B, BAX, BBX, XB, XX = even semester
    is_even = suffix.startswith("B") or suffix.endswith("B") or suffix in ("XX", "XB")
    semester = str(base_sem + (1 if is_even else 0))
    
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
    
    # Credit category from suffix pattern
    if suffix in ("A", "B"):
        credit_category = "4"
    elif suffix in ("A*", "B*"):
        credit_category = "0"
    elif suffix.endswith("XX") or suffix.endswith("AX") or suffix.endswith("BX") or suffix in ("AXX", "ABX", "BAX", "BBX"):
        credit_category = "5"
    else:
        credit_category = "4"
    
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
    faculty_email: str = Field(min_length=3, max_length=254)
    course_title: str = Field(min_length=3, max_length=150)
    course_code: str = Field(min_length=8, max_length=12)  # e.g., UE25CS242B
    raw_course_content: str = Field(min_length=50)
    text_books: str = Field(min_length=5)
    reference_books: str = ""
    preferred_tools: str = ""

    @field_validator("faculty_email", "course_title", "course_code", "raw_course_content", "text_books", "reference_books", "preferred_tools", mode="before")
    @classmethod
    def strip(cls, value):
        return value.strip() if isinstance(value, str) else value
