_HOURS_MAP = {
    "5": {"lecture_hours": 4, "tutorial_hours": 0, "practical_hours": 2, "self_study": 5, "credits": 5},
    "4": {"lecture_hours": 4, "tutorial_hours": 0, "practical_hours": 0, "self_study": 4, "credits": 4},
    "2": {"lecture_hours": 2, "tutorial_hours": 0, "practical_hours": 0, "self_study": 2, "credits": 2},
    "0": {"lecture_hours": 0, "tutorial_hours": 0, "practical_hours": 0, "self_study": 0, "credits": 0},
}

_PROGRAM_MAP = {
    "CSE": "B. TECH",
    "AIML": "B. TECH",
    "ECE": "B. TECH",
    "ME": "B. TECH",
    "EEE": "B. TECH",
    "BT": "B. TECH",
}

_COURSE_TYPE_MAP = {
    "0": "Foundation Course",
    "5": "Core Course-Lab Integrated",
    "4": "Core Course",
    "2": "Core Theory",
}


def compute_hours(cat: str) -> dict:
    result = _HOURS_MAP.get(cat)
    if result is None:
        raise ValueError(f"Unknown credit_category: {cat!r}. Expected one of: {sorted(_HOURS_MAP)}")
    return result


def compute_program(dept: str) -> str:
    result = _PROGRAM_MAP.get(dept)
    if result is None:
        raise ValueError(f"Unknown department: {dept!r}. Expected one of: {sorted(_PROGRAM_MAP)}")
    return result


def compute_course_type(cat: str) -> str:
    result = _COURSE_TYPE_MAP.get(cat)
    if result is None:
        raise ValueError(f"Unknown credit_category: {cat!r}. Expected one of: {sorted(_COURSE_TYPE_MAP)}")
    return result
