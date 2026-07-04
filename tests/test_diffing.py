import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.diffing import apply_patch, build_patch, diff_course, merge_fields, validate_draft


def test_build_and_apply_patch():
    old = {"title": "A", "items": ["one"]}
    new = {"title": "B", "items": ["one", "two"]}

    patch = build_patch(old, new)

    assert apply_patch(old, patch) == new


def test_equivalent_protected_numbers_are_not_blocked():
    base = {"credits": "4", "course_type": "Core Course"}
    proposed = merge_fields(base, {"credits": 4, "course_type": "Core Course"})

    assert validate_draft(base, proposed) == []
    assert proposed["credits"] == "4"


def test_syllabus_topics_added_and_removed_are_reported():
    old = {"units": [{"title": "Unit 1", "content": "Stacks, Queues, Trees"}]}
    new = {"units": [{"title": "Unit 1", "content": "Stacks, Graphs, Trees"}]}

    summary = diff_course(old, new)

    assert "graphs" in summary["topics_added"]
    assert "queues" in summary["topics_removed"]
    assert summary["syllabus_change_percent"] > 0
