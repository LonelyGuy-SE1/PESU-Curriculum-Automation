from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse
import html


router = APIRouter()


def clean(value: str) -> str:
    return value.strip()


def validate_submission(data: dict) -> list[str]:
    issues = []

    if len(data["faculty_name"]) < 2:
        issues.append("Faculty name is too short.")

    if "@" not in data["faculty_email"]:
        issues.append("Faculty email is invalid.")

    if len(data["offering_department"]) < 2:
        issues.append("Offering department is required.")

    if len(data["target_department"]) < 2:
        issues.append("Target department or program is required.")

    if data["semester"] < 1 or data["semester"] > 8:
        issues.append("Semester must be between 1 and 8.")

    if data["credit_category"] not in [0, 2, 4, 5]:
        issues.append("Credit category must be 0, 2, 4, or 5.")

    if len(data["course_title"]) < 3:
        issues.append("Course title is too short.")

    if len(data["raw_course_content"]) < 50:
        issues.append("Course content is too short. Add more unit-level detail.")

    if len(data["text_books"]) < 5:
        issues.append("At least one textbook reference is required.")

    return issues


@router.post("/submissions", response_class=HTMLResponse)
def receive_submission(
    faculty_name: str = Form(...),
    faculty_email: str = Form(...),
    offering_department: str = Form(...),
    target_department: str = Form(...),
    semester: int = Form(...),
    course_title: str = Form(...),
    credit_category: int = Form(...),
    raw_course_content: str = Form(...),
    text_books: str = Form(...),
    reference_books: str = Form(""),
    preferred_tools: str = Form(""),
):
    data = {
        "faculty_name": clean(faculty_name),
        "faculty_email": clean(faculty_email),
        "offering_department": clean(offering_department),
        "target_department": clean(target_department),
        "semester": semester,
        "course_title": clean(course_title),
        "credit_category": credit_category,
        "raw_course_content": clean(raw_course_content),
        "text_books": clean(text_books),
        "reference_books": clean(reference_books),
        "preferred_tools": clean(preferred_tools),
    }

    issues = validate_submission(data)

    if issues:
        issue_items = "".join(f"<li>{html.escape(issue)}</li>" for issue in issues)

        return f"""
        <html>
            <body>
                <h1>Submission Rejected</h1>
                <p>The form was received, but it failed backend checks.</p>
                <ul>{issue_items}</ul>
                <a href="/">Return to form</a>
            </body>
        </html>
        """

    return f"""
    <html>
        <body>
            <h1>Submission Received</h1>

            <p><strong>Faculty:</strong> {html.escape(data["faculty_name"])}</p>
            <p><strong>Email:</strong> {html.escape(data["faculty_email"])}</p>
            <p><strong>Offering Department:</strong> {html.escape(data["offering_department"])}</p>
            <p><strong>Target Department:</strong> {html.escape(data["target_department"])}</p>
            <p><strong>Semester:</strong> {data["semester"]}</p>
            <p><strong>Course Title:</strong> {html.escape(data["course_title"])}</p>
            <p><strong>Credit Category:</strong> {data["credit_category"]}</p>

            <h2>Course Content</h2>
            <pre>{html.escape(data["raw_course_content"])}</pre>

            <h2>Textbooks</h2>
            <pre>{html.escape(data["text_books"])}</pre>

            <h2>Reference Books</h2>
            <pre>{html.escape(data["reference_books"])}</pre>

            <h2>Preferred Tools</h2>
            <pre>{html.escape(data["preferred_tools"])}</pre>

            <a href="/">Submit another course</a>
        </body>
    </html>
    """