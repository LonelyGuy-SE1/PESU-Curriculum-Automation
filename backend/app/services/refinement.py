import logging
import re

from app.supabase import first_row, supabase
from app.services.books import parse_books, raw_book_section
from app.services.curriculum import invalidate_curriculum_cache
from app.services.deterministic import compute_hours, compute_program, compute_course_type
from app.services.openrouter import call as llm

logger = logging.getLogger(__name__)

WORD = re.compile(r"\w+")
UNIT_LINE = re.compile(r"\b(Unit\s+\d+|Module\s+(?:\d+|[IVX]+))\s*[:.-]?\s*(.*)$", re.IGNORECASE)
HOURS_SUFFIX = re.compile(r"\s*\b\d+\s+Hours?\b\s*$", re.IGNORECASE)
DESIRABLE_LINE = re.compile(r"\bDesirable\s+([^\n]+)", re.IGNORECASE)
COURSE_CODE = re.compile(r"\bCourse\s+Code\s*:?\s*([A-Z0-9]+)", re.IGNORECASE)
PAGE_NOISE = re.compile(
    r"P\.?\s*E\.?\s*S\.?\s*University|"
    r"Curriculum|"
    r"\s*:-\s*[A-Za-z]*\s*\d{4}\s*-\s*\d{4}\b|"
    r"\b\d+\s*\|\s*Page\b",
    re.IGNORECASE,
)

SYS = """You refine PES University course submissions for the UG curriculum template.
Return only valid JSON. No markdown. No commentary.
Priority order:
1. Preserve the submitted academic content.
2. Correct spelling, grammar, casing, and formatting.
3. Fill missing template fields from the submitted course scope.
4. Return the required JSON shape.

Editing rules:
- Refine, do not rewrite. If the input is already curriculum-ready, keep its wording and structure except for small correctness fixes.
- If prelude, objectives, outcomes, units, tools, or books are already present, clean them instead of replacing them.
- Generate a field only when that field is missing, incomplete, or too rough for the template.
- Preserve every syllabus topic and subtopic from Raw Course Content.
- Do not summarize away, omit, replace, merge away, or simplify syllabus topics.
- Do not add advanced, fashionable, or unrelated topics.
- Do not invent course codes, books, references, departments, credits, or external prerequisites.
- Correct course title typos, casing, spacing, and grammar.
- Keep objectives and outcomes direct, concise, and aligned with the submitted scope.
- Return exactly 4 units. If the input already has 4 units, keep those boundaries. If it has a different structure, redistribute topics in order without dropping content.
- Unit hours must sum to the supplied total unit hours.
- For tools/languages, use Preferred Tools / Languages when provided; otherwise identify course-specific tools, languages, platforms, or AI tools from Raw Course Content.
- Do not use canned defaults for tools/languages.
- For desirable knowledge, use only relevant knowledge from Previously Completed Courses. Return an empty string when none apply.
- Generate laboratory experiments only when practical hours are non-zero. Keep them tied to submitted topics.
- Copy and clean books from the submitted book fields only.
- Use empty strings or empty arrays for truly unavailable optional content. Do not output "-".
"""

SCHEMA = """{
  "course_title": "corrected course title",
  "prelude": "one short paragraph",
  "objectives": ["3 to 4 objectives"],
  "course_outcomes": ["3 to 4 measurable outcomes"],
  "units": [{"title": "Unit 1: Title", "content": "compact topic list", "hours": 14}],
  "lab_experiments": ["concise lab item"],
  "tools_languages": "course-specific tools, languages, platforms, or AI tools",
  "desirable_knowledge": "short text based only on previously completed courses, or empty string",
  "text_books": ["submitted text books only"],
  "reference_books": ["submitted reference books only"]
}"""

EXAMPLES = """Behavior examples calibrated to PESU curriculum style.
Use them only to learn fidelity, field shape, and level of detail. Do not copy example facts into the real answer.

Example 1: already refined input
Input:
Course Title: Web Technologies
Weekly Hours: L 4, T 0, P 0, S 4, C 4
Total Unit Hours: 56
Raw Course Content:
Unit 1: HTML, CSS and Client-Side Scripting - web architecture, HTTP request and response formats, URLs, HTML elements and attributes, web forms, HTML5 tags and controls, CSS selectors, style properties, box model, JavaScript objects, DOM manipulation, events and event handling. 14 Hours
Unit 2: HTML5 and ReactJS - HTML5 APIs, audio, video, progress, geolocation, callbacks, promises, single page applications, XML vs JSON, async/await, JSX, rendering elements, React setup, components, styling, props, state and context. 14 Hours
Unit 3: ReactJS and NodeJS - complex state management, keys, event handling, forms, hooks including useState, useRef, useEffect, useContext and useReducer, React Router, introduction to NextJS, NodeJS architecture, callbacks, modules, buffers, streams, file system and Axios API. 14 Hours
Unit 4: MongoDB and ExpressJS - documents, collections, reading and writing to MongoDB, MongoDB NodeJS driver, running a React application on NodeJS, React Router, web services, REST APIs, Express routing, URL building, error handling, middleware, form data and file upload. 14 Hours
Preferred Tools / Languages: HTML, CSS, JavaScript, MERN Technologies, GitHub, AI tools: Copilot and Tabnine
Previously Completed Courses: None
Text Books:
1. Robin Nixon, Learning PHP, MySQL and JavaScript, 5th Edition, O'Reilly Media, 2018.
2. Vasan Subramanian, Pro MERN Stack: Full Stack Web App Development with Mongo, Express, React, and Node, Apress, 2017.
Output:
{
  "course_title": "Web Technologies",
  "prelude": "This course develops an in-depth understanding of technologies required to design and develop rich web applications using client-side scripting, ReactJS, NodeJS, ExpressJS, and MongoDB.",
  "objectives": ["Build web pages using HTML, CSS, JavaScript, and advanced JavaScript concepts.", "Use HTML5, AJAX, JSON, and ReactJS to develop interactive user interfaces.", "Build multi-tier applications by connecting ReactJS interfaces to NodeJS services.", "Integrate MongoDB through ExpressJS and RESTful web services."],
  "course_outcomes": ["Develop web pages using HTML, CSS, JavaScript, DOM manipulation, and event handling.", "Create interactive user interfaces using HTML5 APIs and ReactJS components.", "Implement server-side functionality using NodeJS, modules, streams, file system APIs, and routing.", "Create RESTful services with ExpressJS and integrate MongoDB for persistent storage."],
  "units": [
    {"title": "Unit 1: HTML, CSS and Client-Side Scripting", "content": "Web architecture, HTTP request and response formats, URLs, HTML elements and attributes, web forms, HTML5 tags and controls, CSS selectors, style properties, box model, JavaScript objects, DOM manipulation, events and event handling.", "hours": 14},
    {"title": "Unit 2: HTML5 and ReactJS", "content": "HTML5 APIs, audio, video, progress, geolocation, callbacks, promises, single page applications, XML vs JSON, async/await, JSX, rendering elements, React setup, components, styling, props, state and context.", "hours": 14},
    {"title": "Unit 3: ReactJS and NodeJS", "content": "Complex state management, keys, event handling, forms, hooks including useState, useRef, useEffect, useContext and useReducer, React Router, introduction to NextJS, NodeJS architecture, callbacks, modules, buffers, streams, file system and Axios API.", "hours": 14},
    {"title": "Unit 4: MongoDB and ExpressJS", "content": "Documents, collections, reading and writing to MongoDB, MongoDB NodeJS driver, running a React application on NodeJS, React Router, web services, REST APIs, Express routing, URL building, error handling, middleware, form data and file upload.", "hours": 14}
  ],
  "lab_experiments": [],
  "tools_languages": "HTML, CSS, JavaScript, MERN Technologies, GitHub; AI tools: Copilot, Tabnine",
  "desirable_knowledge": "",
  "text_books": ["Robin Nixon, Learning PHP, MySQL and JavaScript, 5th Edition, O'Reilly Media, 2018.", "Vasan Subramanian, Pro MERN Stack: Full Stack Web App Development with Mongo, Express, React, and Node, Apress, 2017."],
  "reference_books": []
}

Example 2: detailed lab-integrated input with title and formatting issues
Input:
Course Title: data structures & its aplications
Weekly Hours: L 4, T 0, P 2, S 5, C 5
Total Unit Hours: 56
Raw Course Content:
Unit 1: Linked List and Stacks - Review of C, static and dynamic memory allocation, doubly linked list, circular linked list, multilist and sparse matrix, skip list dictionary case study, stack using arrays and linked list, function execution, nested functions, recursion, Tower of Hanoi, infix to postfix, infix to prefix, expression evaluation, matching parenthesis. 14 Hours
Unit 2: Queues and Trees - simple queue, circular queue, priority queue, dequeue using arrays and linked list, Josephus problem, CPU scheduling using queues, N-ary trees, binary trees, binary search trees, forests, conversion to binary tree, preorder, inorder and postorder traversal. 14 Hours
Unit 3: Application of Trees and Introduction to Graphs - BST insertion and deletion using arrays and dynamic allocation, binary expression tree, threaded binary search tree, heaps, priority queue using min heap and max heap, dictionary and decision tree applications, AVL trees, rotations, splay tree, graph properties, adjacency matrix, adjacency list, DFS, BFS, network topology representation. 14 Hours
Unit 4: Applications of Graphs, B-Trees, Suffix Tree and Hashing - BFS and DFS applications, connectivity, path finding in a network, suffix trees, trie trees, insert, delete and search operations, hashing, hash functions, hash tables, separate chaining, open addressing, double hashing, rehashing, URL decoding and word prediction using trie trees and suffix trees. 14 Hours
Laboratory: linked list operations; stack applications; queue applications; binary tree and BST applications; graph data structure applications; hashing techniques.
Preferred Tools / Languages: C-Programming language; AI tools: VisuAlgo (Interactive Visualizations), Algorithm Visualizer (AI Explanations)
Previously Completed Courses: Problem Solving with C
Text Books: 1. Langsam Yedidyah, Moshe J. Augenstein, Aaron M. Tenenbaum, Data Structures using C / C++, Pearson Education Inc., 2nd Edition, 2015.
Output:
{
  "course_title": "Data Structures and Applications",
  "prelude": "This course introduces fundamental data structure concepts with emphasis on their theoretical foundations, implementation techniques, and practical applications using a programming language.",
  "objectives": ["Analyze and design data structures for efficient storage, retrieval, and manipulation.", "Use linked lists, stacks, queues, trees, heaps, and graphs for suitable computational tasks.", "Implement insertion, deletion, searching, and modification operations across linear and non-linear data structures.", "Select and apply appropriate data structures to solve application-oriented problems."],
  "course_outcomes": ["Select and apply appropriate data structures for solving problems across application domains.", "Implement fundamental data structures and their operations using suitable programming constructs.", "Use data structures effectively to design efficient solutions for computational problems.", "Develop software components by applying data structure principles and their applications."],
  "units": [
    {"title": "Unit 1: Linked List and Stacks", "content": "Review of C, static and dynamic memory allocation, doubly linked list, circular linked list, multilist and sparse matrix, skip list dictionary case study, stack using arrays and linked list, function execution, nested functions, recursion, Tower of Hanoi, infix to postfix, infix to prefix, expression evaluation, matching parenthesis.", "hours": 14},
    {"title": "Unit 2: Queues and Trees", "content": "Simple queue, circular queue, priority queue, dequeue using arrays and linked list, Josephus problem, CPU scheduling using queues, N-ary trees, binary trees, binary search trees, forests, conversion to binary tree, preorder, inorder and postorder traversal.", "hours": 14},
    {"title": "Unit 3: Application of Trees and Introduction to Graphs", "content": "BST insertion and deletion using arrays and dynamic allocation, binary expression tree, threaded binary search tree, heaps, priority queue using min heap and max heap, dictionary and decision tree applications, AVL trees, rotations, splay tree, graph properties, adjacency matrix, adjacency list, DFS, BFS, network topology representation.", "hours": 14},
    {"title": "Unit 4: Applications of Graphs, B-Trees, Suffix Tree and Hashing", "content": "BFS and DFS applications, connectivity, path finding in a network, suffix trees, trie trees, insert, delete and search operations, hashing, hash functions, hash tables, separate chaining, open addressing, double hashing, rehashing, URL decoding and word prediction using trie trees and suffix trees.", "hours": 14}
  ],
  "lab_experiments": ["Linked list and advanced operations.", "Stack applications.", "Queue applications.", "Binary tree and binary search tree applications.", "Graph data structure applications.", "Hashing techniques."],
  "tools_languages": "C-Programming language; AI tools: VisuAlgo (Interactive Visualizations), Algorithm Visualizer (AI Explanations)",
  "desirable_knowledge": "Problem Solving with C",
  "text_books": ["Langsam Yedidyah, Moshe J. Augenstein, Aaron M. Tenenbaum, Data Structures using C / C++, Pearson Education Inc., 2nd Edition, 2015."],
  "reference_books": []
}
"""


def _lines(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def _clean_noise(value: str) -> str:
    return re.sub(r"\s+", " ", PAGE_NOISE.sub(" ", value)).strip()


def _books(*values) -> list[str]:
    return parse_books(*values)


def _raw_book_section(raw_content: str, kind: str) -> str:
    return raw_book_section(raw_content, kind)


def _words(text: str) -> int:
    return len(WORD.findall(text))


def _clean_part(value: str) -> str:
    return _clean_noise(value.strip(" \t-*\u2022"))


def _split_parts(text: str) -> list[str]:
    lines = [_clean_part(line) for line in text.splitlines() if _clean_part(line)]
    if len(lines) >= 4:
        return lines
    compact = _clean_part(text)
    parts = [_clean_part(part) for part in re.split(r"(?<=[.!?])\s+", compact) if _clean_part(part)]
    if len(parts) >= 4:
        return parts
    words = compact.split()
    if not words:
        return []
    return [
        " ".join(words[(index * len(words)) // 4 : ((index + 1) * len(words)) // 4])
        for index in range(4)
    ]


def _four_units_from_raw(raw_content: str) -> list[dict]:
    parts = _split_parts(raw_content)
    if not parts:
        return []
    buckets = [[] for _ in range(4)]
    for index, part in enumerate(parts):
        buckets[min(index * 4 // len(parts), 3)].append(part)
    return [
        {"title": f"Unit {index + 1}", "content": " ".join(bucket).strip(), "hours": 0}
        for index, bucket in enumerate(buckets)
        if bucket
    ]


def _course_contents(raw_content: str) -> str:
    lines = raw_content.splitlines()
    start = None
    for index, line in enumerate(lines):
        if "Course" in line and "Contents" in line:
            start = index
            break
        if "Course" in line and any("Contents" in item for item in lines[index + 1 : index + 3]):
            start = index
            break
    if start is None:
        return raw_content

    end = len(lines)
    for index in range(start + 1, len(lines)):
        marker = lines[index].strip()
        if not marker:
            continue
        if any(marker.startswith(label) for label in ("Laboratory", "Text Book", "Reference", "Course Outcome", "Assignment /")):
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def _syllabus_line(line: str) -> str:
    clean = _clean_part(line)
    clean = re.sub(r"^(Course\s+Contents|Contents)\s+", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^Course\s+(?=Unit\s+\d+|Module\s+(?:\d+|[IVX]+))", "", clean, flags=re.IGNORECASE)
    return HOURS_SUFFIX.sub("", clean).strip()


def _units_from_course_contents(raw_content: str, fallback: bool = True) -> list[dict]:
    content = _course_contents(raw_content)
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    units = []
    current = None

    for line in lines:
        clean = _syllabus_line(line)
        if not clean:
            continue
        match = UNIT_LINE.search(clean)
        if match:
            if current:
                units.append(current)
            label = match.group(1).strip().title()
            rest = match.group(2).strip(" :-")
            if " - " in rest:
                title, inline_content = rest.split(" - ", 1)
            elif _words(rest) > 12:
                title, inline_content = "", rest
            else:
                title, inline_content = rest, ""
            current = {
                "title": f"{label}: {title.strip()}" if title.strip() else label,
                "content": inline_content.strip(),
                "hours": 0,
            }
            continue
        if current:
            current["content"] = f"{current['content']} {clean}".strip()

    if current:
        units.append(current)
    if len(units) == 4:
        return units
    return _four_units_from_raw(content) if fallback else []


def _unit_text(unit: dict) -> str:
    title = str(unit.get("title", "")).strip()
    content = str(unit.get("content", "")).strip()
    if title and content:
        return f"{title}: {content}"
    return title or content


def _fit_four_units(units: list[dict], raw_content: str) -> list[dict]:
    raw = _course_contents(raw_content).strip()
    raw_units = _units_from_course_contents(raw_content, fallback=False)
    raw_unit_words = _words(" ".join(_unit_text(unit) for unit in raw_units))
    if raw_units and raw_unit_words >= _words(raw) * 0.7:
        return raw_units
    if raw and _words(" ".join(_unit_text(unit) for unit in units)) < _words(raw) * 0.8:
        return raw_units or _units_from_course_contents(raw_content)
    if len(units) > 4:
        fourth = units[3].copy()
        fourth["content"] = " ".join(_unit_text(unit) for unit in units[3:]).strip()
        return units[:3] + [fourth]
    if len(units) == 4:
        return units
    if raw:
        return raw_units or _units_from_course_contents(raw_content)
    return units


def _units(value) -> list[dict]:
    units = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        content = str(item.get("content", "")).strip()
        hours_raw = str(item.get("hours", "0"))
        hours = int("".join(ch for ch in hours_raw if ch.isdigit()) or 0)
        if title or content:
            units.append({"title": title, "content": content, "hours": hours})
    return units


def _assign_hours(units: list[dict], total_hours: int) -> list[dict]:
    if not units:
        return units
    if sum(unit["hours"] for unit in units) == total_hours:
        return units
    base, extra = divmod(total_hours, len(units))
    for index, unit in enumerate(units):
        unit["hours"] = base + (1 if index < extra else 0)
    return units


def _text(*values) -> str:
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text and text != "-":
                return text
    return ""


def _course_code(raw_content: str) -> str:
    match = COURSE_CODE.search(raw_content or "")
    return match.group(1).upper() if match else ""


def _prior_course_titles(sub: dict) -> list[str]:
    semester = int(sub["semester"])
    if semester <= 1:
        return []
    rows = (
        supabase.table("refined_submissions")
        .select("submission_id,course_code,course_title,semester")
        .lt("semester", semester)
        .order("semester")
        .execute()
        .data
    )
    ids = [row["submission_id"] for row in rows if row.get("submission_id")]
    submissions = supabase.table("submissions").select("id,target_department,raw_course_content").in_("id", ids).execute().data if ids else []
    departments = {row["id"]: row.get("target_department") for row in submissions}
    raw_codes = {row["id"]: _course_code(row.get("raw_course_content") or "") for row in submissions}
    titles = []
    for row in rows:
        if departments.get(row.get("submission_id")) != sub.get("target_department"):
            continue
        title = str(row.get("course_title") or "").strip()
        code = str(row.get("course_code") or raw_codes.get(row.get("submission_id")) or "").strip()
        label = f"{code} - {title}" if code else title
        if title and label not in titles:
            titles.append(label)
    return titles


def _normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _singularized(text: str) -> str:
    return " ".join(word[:-1] if len(word) > 3 and word.endswith("s") else word for word in _normalized(text).split())


def _core_key(text: str) -> str:
    skip = {"a", "an", "and", "for", "in", "its", "of", "the", "to", "with"}
    return " ".join(word for word in _singularized(text).split() if word not in skip)


def _prior_keys(course: str) -> list[str]:
    match = re.match(r"\s*([A-Z]{2}\d{2}[A-Z0-9]+)\s*[-:]\s*(.+)", course)
    code = match.group(1).lower() if match else ""
    title = match.group(2) if match else course
    return [key for key in (code, _normalized(title), _singularized(title), _core_key(title)) if key]


def _prior_matches(text: str, prior_courses: list[str]) -> str:
    normalized = _normalized(text)
    singularized = _singularized(text)
    core = _core_key(text)
    matches = [course for course in prior_courses if any(key in normalized or key in singularized or key in core for key in _prior_keys(course))]
    return ", ".join(matches)


def _submitted_desirable(raw_content: str, prior_courses: list[str]) -> str | None:
    match = DESIRABLE_LINE.search(raw_content or "")
    if not match:
        return None
    value = _text(match.group(1))
    if not value:
        return ""
    return _prior_matches(value, prior_courses) or None


def _desirable(value, prior_courses: list[str], raw_content: str = "") -> str:
    if not prior_courses:
        return ""
    submitted = _submitted_desirable(raw_content, prior_courses)
    if submitted is not None:
        return submitted
    return _prior_matches(_text(value), prior_courses)


def _courses_text(courses: list[str]) -> str:
    return "\n".join(f"- {course}" for course in courses) if courses else "None"


def build_refined_payload(sub: dict, out: dict, prior_courses: list[str] | None = None) -> dict:
    out = out or {}
    prior_courses = prior_courses or []
    det = compute_hours(sub["credit_category"])
    total_unit_hours = det["lecture_hours"] * 14
    raw_content = sub.get("raw_course_content") or ""
    text_book_source = _raw_book_section(raw_content, "text") or sub["text_books"]
    reference_book_source = _raw_book_section(raw_content, "reference") or sub.get("reference_books")
    units = _assign_hours(_fit_four_units(_units(out.get("units")), sub.get("raw_course_content") or ""), total_unit_hours)

    objectives = _lines(out.get("objectives"))[:4]
    course_outcomes = _lines(out.get("course_outcomes"))[:4] or objectives

    from app.services.elective_categorization import is_elective_course

    code = _course_code(raw_content) or sub["course_code"]
    return {
        "submission_id": sub["id"],
        "semester": int(sub["semester"]),
        "course_code": code,
        "course_title": _text(out.get("course_title"), sub["course_title"]),
        "program": compute_program(sub["target_department"]),
        "course_type": compute_course_type(sub["credit_category"]),
        "is_elective": is_elective_course({"course_code": code, "semester": sub["semester"]}),
        **det,
        "prelude": _text(out.get("prelude"), f"This course covers {sub['course_title'].strip()}."),
        "objectives": objectives,
        "course_outcomes": course_outcomes,
        "units": units,
        "lab_experiments": _lines(out.get("lab_experiments"))[:10] if det["practical_hours"] else [],
        "tools_languages": _text(out.get("tools_languages"), sub.get("preferred_tools")),
        "desirable_knowledge": _desirable(out.get("desirable_knowledge"), prior_courses, raw_content),
        "text_books": _books(text_book_source),
        "reference_books": _books(reference_book_source),
        "status": "refined",
    }


def refine(submission_id: int):
    sub = first_row(supabase.table("submissions").select("*").eq("id", submission_id))
    if not sub:
        raise LookupError("Submission not found")
    det = compute_hours(sub["credit_category"])
    ctype = compute_course_type(sub["credit_category"])
    total_unit_hours = det["lecture_hours"] * 14
    prior_courses = _prior_course_titles(sub)

    prompt = f"""Return JSON matching this schema. Include every key:
{SCHEMA}

{EXAMPLES}

Now refine the real submission below.

Course Title: {sub["course_title"]}
Offering Department: {sub["offering_department"]}
Target Department: {sub["target_department"]}
Semester: {sub["semester"]}
Credit Category: {sub["credit_category"]}
Course Type: {ctype}
Weekly Hours: L {det["lecture_hours"]}, T {det["tutorial_hours"]}, P {det["practical_hours"]}, S {det["self_study"]}, C {det["credits"]}
Total Unit Hours: {total_unit_hours}
Raw Course Content:
{sub["raw_course_content"]}

Previously Completed Courses:
{_courses_text(prior_courses)}

Text Books:
{sub["text_books"]}

Reference Books:
{sub.get("reference_books") or "-"}

Preferred Tools / Languages:
{sub.get("preferred_tools") or "-"}"""

    out = llm(SYS, prompt)
    merged = build_refined_payload(sub, out, prior_courses)

    existing = supabase.table("refined_submissions").select("id").eq("submission_id", submission_id).execute().data
    if existing:
        supabase.table("refined_submissions").update(merged).eq("submission_id", submission_id).execute()
        refined_id = existing[0]["id"]
    else:
        refined_id = supabase.table("refined_submissions").insert(merged).execute().data[0]["id"]

    supabase.table("submissions").update({"status": "refined"}).eq("id", submission_id).execute()
    invalidate_curriculum_cache()

    if merged["is_elective"]:
        try:
            from app.services.elective_categorization import categorize_refined_elective
            categorize_refined_elective(int(refined_id))
        except Exception:
            logger.exception("Elective categorization failed for refined_id=%s", refined_id)

    return merged
