import difflib
import json
import re
from copy import deepcopy
from typing import Any

PROTECTED_FIELDS = {
    "program",
    "lecture_hours",
    "tutorial_hours",
    "practical_hours",
    "self_study",
    "credits",
    "course_type",
}

TOPIC_SPLIT = re.compile(r"[,;\n]+")
SPACE = re.compile(r"\s+")


def stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)


def build_patch(old: Any, new: Any, path: str = "") -> list[dict]:
    if isinstance(old, dict) and isinstance(new, dict):
        patch = []
        old_keys = set(old)
        new_keys = set(new)
        for key in sorted(old_keys - new_keys):
            patch.append({"op": "remove", "path": f"{path}/{_escape(key)}"})
        for key in sorted(new_keys - old_keys):
            patch.append({"op": "add", "path": f"{path}/{_escape(key)}", "value": new[key]})
        for key in sorted(old_keys & new_keys):
            patch.extend(build_patch(old[key], new[key], f"{path}/{_escape(key)}"))
        return patch

    if old != new:
        return [{"op": "replace", "path": path or "/", "value": new}]
    return []


def apply_patch(value: Any, patch: list[dict]) -> Any:
    result = deepcopy(value)
    for op in patch:
        name = op.get("op")
        path = op.get("path")
        if name not in {"add", "remove", "replace"} or not isinstance(path, str):
            raise ValueError("Unsupported patch operation")
        parent, key = _resolve_parent(result, path)
        if isinstance(parent, list):
            index = int(key)
            if name == "remove":
                parent.pop(index)
            elif name == "replace":
                parent[index] = op.get("value")
            else:
                parent.insert(index, op.get("value"))
            continue
        if name == "remove":
            parent.pop(key, None)
        else:
            parent[key] = op.get("value")
    return result


def diff_course(old: dict, new: dict) -> dict:
    old_text = stable_json(old)
    new_text = stable_json(new)
    patch = build_patch(old, new)
    syllabus_old = _syllabus_text(old)
    syllabus_new = _syllabus_text(new)
    topics_old = _topics(syllabus_old)
    topics_new = _topics(syllabus_new)

    return {
        "json_patch": patch,
        "patch_operations": len(patch),
        "change_percent": _change_percent(old_text, new_text),
        "syllabus_change_percent": _change_percent(syllabus_old, syllabus_new),
        "topics_added": sorted(topics_new - topics_old),
        "topics_removed": sorted(topics_old - topics_new),
        "protected_changes": sorted(field for field in PROTECTED_FIELDS if _field_value(old, field) != _field_value(new, field)),
        "unified_diff": "\n".join(
            difflib.unified_diff(
                old_text.splitlines(),
                new_text.splitlines(),
                fromfile="current",
                tofile="proposed",
                lineterm="",
            )
        ),
    }


def validate_draft(old: dict, new: dict) -> list[str]:
    issues = []
    for field in PROTECTED_FIELDS:
        if _field_value(old, field) != _field_value(new, field):
            issues.append(f"{field} is deterministic and cannot be changed by an agent draft")
    return issues


def merge_fields(base: dict, fields: dict) -> dict:
    merged = deepcopy(base)
    for key, value in fields.items():
        if key in PROTECTED_FIELDS and str(base.get(key) or "") == str(value or ""):
            value = base.get(key)
        merged[key] = value
    return merged


def _field_value(value: dict, field: str) -> str:
    return str(value.get(field) or "")


def _escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _unescape(value: str) -> str:
    return value.replace("~1", "/").replace("~0", "~")


def _resolve_parent(value: Any, path: str) -> tuple[Any, str]:
    if path in {"", "/"}:
        raise ValueError("Root patch operations are not supported")
    parts = [_unescape(part) for part in path.strip("/").split("/")]
    current = value
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current, parts[-1]


def _change_percent(old: str, new: str) -> float:
    if not old and not new:
        return 0.0
    ratio = difflib.SequenceMatcher(None, old, new).ratio()
    return round((1 - ratio) * 100, 2)


def _syllabus_text(value: dict) -> str:
    units = value.get("units") or []
    if not isinstance(units, list):
        return ""
    parts = []
    for unit in units:
        if isinstance(unit, dict):
            parts.append(str(unit.get("title") or ""))
            parts.append(str(unit.get("content") or ""))
    return SPACE.sub(" ", " ".join(parts)).strip()


def _topics(text: str) -> set[str]:
    topics = set()
    for item in TOPIC_SPLIT.split(text):
        topic = SPACE.sub(" ", item).strip(" .:-").lower()
        if len(topic) >= 4:
            topics.add(topic)
    return topics
