from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CourseSubmission(BaseModel):
    faculty_email: str = Field(min_length=3, max_length=254)
    course_title: str = Field(min_length=3, max_length=150)
    offering_department: Literal["MA", "CS", "UZ"]
    target_department: Literal["CSE", "ECE", "ME", "BT", "EEE", "AIML"]
    semester: Literal["1", "2", "3", "4", "5", "6", "7", "8"]
    credit_category: Literal["0", "2", "4", "5"]
    raw_course_content: str = Field(min_length=50)
    text_books: str = Field(min_length=5)
    reference_books: str = ""
    preferred_tools: str = ""

    @field_validator("faculty_email", "course_title", "raw_course_content", "text_books", "reference_books", "preferred_tools", mode="before")
    @classmethod
    def strip(cls, value):
        return value.strip() if isinstance(value, str) else value
