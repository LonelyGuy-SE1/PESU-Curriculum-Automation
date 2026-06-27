from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel,Field, field_validator
from typing import Literal
from weasyprint import HTML

from app.preview import build_course_preview
from app.supabase import supabase

router=APIRouter()
templates=Environment(loader=FileSystemLoader("app/templates"))
FRONTEND_DIR=Path(__file__).resolve().parent.parent.parent/"frontend"

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

    @field_validator("faculty_email","course_title","raw_course_content","text_books","reference_books","preferred_tools",mode="before")
    @classmethod
    def strip(cls, v):
        return v.strip() if isinstance(v, str) else v

@router.post("/submissions")
def receive(data: CourseSubmission):
    d=data.model_dump()
    d["status"]="pending"
    r=supabase.table("submissions").insert(d).execute()
    return {"message":"Submission Received!","submission":r.data[0]}

@router.get("/preview/semester/{sem}/courses")
def list_courses(sem:str):
    r=supabase.table("refined_submissions").select("id").execute()
    return {"course_ids":[row["id"] for row in r.data]}

@router.get("/preview/course/{refined_id}")
def preview_course(refined_id:int):
    r=supabase.table("refined_submissions").select("*").eq("id",refined_id).single().execute()
    course=build_course_preview(r.data)
    return HTMLResponse(templates.get_template("jinja_sample.html").render(course=course,curriculum_year="2025-2026",page_number=""))

@router.get("/preview/semester/{sem}/pdf")
def download_pdf(sem:str):
    r=supabase.table("refined_submissions").select("id").execute()
    ids=[row["id"] for row in r.data]
    style=""
    bodies=[]
    for i,rid in enumerate(ids,1):
        r=supabase.table("refined_submissions").select("*").eq("id",rid).single().execute()
        h=templates.get_template("jinja_sample.html").render(course=build_course_preview(r.data),curriculum_year="2025-2026",page_number=str(i))
        if not style:
            s1=h.find("<style");e1=h.find("</style>")+8
            style=h[s1:e1]
            s2=h.find("<style",e1);e2=h.find("</style>",s2)+8
            style+=h[s2:e2]
        bs=h.find(">",h.find("<body"))+1;be=h.find("</body>")
        cls="page-break" if i>1 else ""
        bodies.append(f"<div class=\"{cls}\">{h[bs:be]}</div>"if cls else h[bs:be])
    combined=f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{style}<style>@page{{size:A4;margin:0;}}.page-break{{page-break-before:always;}}.c71{{padding-bottom:35pt;}}</style></head><body>{"".join(bodies)}</body></html>"""
    pdf=HTML(string=combined,base_url=str(FRONTEND_DIR)).write_pdf()
    return Response(content=pdf,media_type="application/pdf",headers={"Content-Disposition":f"attachment;filename=semester-{sem}.pdf"})
