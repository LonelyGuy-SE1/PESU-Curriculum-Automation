from app.routes.versions import _course_summary


def test_course_summary_uses_snapshot_fields():
    row = {
        "id": 4,
        "refined_id": 9,
        "course_json": {"semester": "3", "course_code": "CS201", "course_title": "Data Structures"},
    }

    assert _course_summary(row) == {
        "id": 4,
        "refined_id": 9,
        "semester": "3",
        "course_code": "CS201",
        "course_title": "Data Structures",
    }
