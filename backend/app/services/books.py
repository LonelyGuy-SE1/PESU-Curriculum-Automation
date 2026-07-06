import re

WORD = re.compile(r"\w+")
BOOK_STOP = re.compile(
    r"\bCourse\b[\s\S]{0,160}\bOutcome\b|"
    r"\b(Course\s+Objectives?|Assignment\s*/|Laboratory|Recommended\s+Materials)\b",
    re.IGNORECASE,
)
BOOK_LABEL = re.compile(
    r"(?im)^\s*(?:Text\s*)?Book\(s\):\s*|"
    r"^\s*Text\s+Book\(s\):\s*|"
    r"^\s*Reference\s*(?:Book\(s\):)?\s*"
)
BOOK_NUMBER = re.compile(r"(?:^|\n|\s{2,}|(?<=\.)\s+)\d+\s*[:.)]\s*")
ORDINAL_LINE = re.compile(r"(?im)^\s*(st|nd|rd|th)\s*$")
PAGE_NOISE = re.compile(
    r"P\.?\s*E\.?\s*S\.?\s*University|"
    r"Curriculum|"
    r"\s*:-\s*[A-Za-z]*\s*\d{4}\s*-\s*\d{4}\b|"
    r"\b\d+\s*\|\s*Page\b",
    re.IGNORECASE,
)
TEXT_BOOK_LINE = re.compile(r"\bText\s+Book\(s\):", re.IGNORECASE)
REFERENCE_LINE = re.compile(r"^\s*Reference\b", re.IGNORECASE)
SECTION_END_LINE = re.compile(r"^\s*(Course\s+Outcome|Assignment\s*/|Course\s+Objectives?|Laboratory)\b", re.IGNORECASE)


def _words(text: str) -> int:
    return len(WORD.findall(text))


def _flatten(values) -> str:
    parts = []
    for value in values:
        if not value:
            continue
        if isinstance(value, list):
            parts.extend(str(item) for item in value if str(item).strip())
        else:
            parts.append(str(value))
    text = "\n".join(parts)
    match = BOOK_STOP.search(text)
    if match:
        text = text[: match.start()]
    text = ORDINAL_LINE.sub("", text)
    text = PAGE_NOISE.sub("\n", text)
    return BOOK_LABEL.sub("", text)


def _clean(value: str) -> str:
    value = BOOK_LABEL.sub("", value)
    value = re.sub(r"\bBook\(s\):?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"-\s+", "-", value)
    return re.sub(r"\s+", " ", value).strip(" :")


def parse_books(*values) -> list[str]:
    text = _flatten(values)
    if not text.strip():
        return []

    numbered = [part for part in BOOK_NUMBER.split(text) if part.strip()]
    if numbered and (len(numbered) > 1 or BOOK_NUMBER.search(text)):
        parts = numbered
    else:
        parts = [line for line in text.splitlines() if line.strip()]

    books = []
    seen = set()
    for part in parts:
        item = _clean(part)
        if not item:
            continue
        if books and (item.startswith("(") or (_words(item) <= 3 and not re.search(r"\b\d{4}\b", item))):
            books[-1] = f"{books[-1]} {item}".strip()
            continue
        key = re.sub(r"[^a-z0-9]+", " ", item.lower()).strip()
        if key not in seen:
            books.append(item)
            seen.add(key)
    return books


def raw_book_section(raw_content: str, kind: str) -> str:
    lines = (raw_content or "").splitlines()
    start = None
    for index, line in enumerate(lines):
        if kind == "text" and TEXT_BOOK_LINE.search(line):
            start = index
            break
        if kind == "reference" and REFERENCE_LINE.search(line):
            start = index
            break
    if start is None:
        return ""

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if kind == "text" and REFERENCE_LINE.search(lines[index]):
            end = index
            break
        if SECTION_END_LINE.search(lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])
