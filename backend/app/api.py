from fastapi import APIRouter
from pydantic import BaseModel,Field, field_validator
from typing import Literal

router=APIRouter()

class CourseSubmission(BaseModel):
    faculty_email: str=Field(min_length=3, max_length=254)
    course_title: str=Field(min_length=3, max_length=150)
    offering_department: Literal["MA", "CS", "UZ"]
    target_department: Literal["CSE", "ECE", "ME", "BT", "EEE", "AIML"]
    semester: Literal["1", "2", "3", "4", "5", "6", "7", "8"]
    credit_category: Literal["0", "2", "4", "5"]
    raw_course_content: str=Field(min_length=50)
    text_books: str=Field(min_length=5)
    reference_books: str=""
    preferred_tools: str=""

    @field_validator(
        "faculty_email", "course_title", "raw_course_content", "text_books", "reference_books", "preferred_tools", mode="before",)
    @classmethod
    def strip(cls, v):
        return v.strip() if isinstance(v, str) else v
    
@router.post("/submissions")
def receive(data: CourseSubmission):
    print("=== NEW SUBMISSION ===")
    for field, values in data.model_dump().items():
        print(f"{field}: {values}")
    print("======================")
    return {"message": "Submission received successfully!", "submission": data.model_dump()}