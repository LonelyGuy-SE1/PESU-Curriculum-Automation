---
title: Curriculum Backend
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# Syntagma

<div align="center">

![Python](https://img.shields.io/badge/python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/fastapi-0.138-009688?style=flat-square&logo=fastapi&logoColor=white)
![Supabase](https://img.shields.io/badge/supabase-postgres-3FCF8E?style=flat-square&logo=supabase&logoColor=white)
![Upstash Redis](https://img.shields.io/badge/upstash--redis-cache-DD0000?style=flat-square&logo=redis&logoColor=white)
![OpenRouter](https://img.shields.io/badge/openrouter--llm-6366F1?style=flat-square&logo=openai&logoColor=white)
![WeasyPrint](https://img.shields.io/badge/weasyprint-pdf-E64B1A?style=flat-square&logo=markdown&logoColor=white)
![CI](https://img.shields.io/badge/CI-passing-brightgreen?style=flat-square&logo=githubactions&logoColor=white)
![Tests](https://img.shields.io/badge/tests-229-green?style=flat-square&logo=pytest&logoColor=white)
![Sentry](https://img.shields.io/badge/sentry--sdk-2.63-362D59?style=flat-square&logo=sentry&logoColor=white)
![HF Space](https://img.shields.io/badge/deploy-HF%20Spaces-yellow?style=flat-square&logo=huggingface&logoColor=white)
![Vercel](https://img.shields.io/badge/frontend-Vercel-black?style=flat-square&logo=vercel&logoColor=white)

</div>

## The Problem

PES University revamps its B.Tech curriculum nearly every academic year. Faculty submit course content in raw, inconsistent formats. Someone manually compiles it into the official syllabus document. There is no version history. There is no way to compare what changed between years. The entire process is manual, error-prone, and slow.

## How Syntagma Solves It

Faculty submit raw course content through a form. The system uses AI to clean and structure it into curriculum-ready records. Admins review, edit, and approve changes through an agentic AI assistant that proposes edits but never applies them without human approval. The full curriculum renders as official A4 PDFs with PES University's letterhead. Every change is tracked with named version snapshots.

**Live Demo:** **[syntagma.lonelyguy.tech](https://syntagma.lonelyguy.tech/)** (preferred)

Backup: [pesucurriculum.vercel.app](https://pesucurriculum.vercel.app/)

## Architecture

```mermaid
flowchart TB
    subgraph Frontend
        Auth["/auth/ Sign In"]
        Dashboard["/ Dashboard"]
        Form["/form/ Course Submission"]
        Courses["/courses/ Course Management"]
        Preview["/preview/ PDF Preview"]
        Editor["/live-editor/ Agentic Editor"]
        Versions["/versions/ Version History"]
        Docs["/docs/ Documentation"]
    end

    subgraph Backend["FastAPI Backend /api"]
        direction TB
        SubAPI["Submissions"]
        CoursesAPI["Courses"]
        PreviewAPI["Preview 8 endpoints"]
        AgentAPI["Agent 13 endpoints"]
        ChatAPI["Chat SSE streaming"]
        VersionsAPI["Versions 10 endpoints"]
    end

    subgraph External
        LLM["OpenRouter Primary + Fallback"]
        Redis[("Upstash Redis")]
        Supa[(Supabase Postgres)]
        WeasyPrint["WeasyPrint A4 PDF"]
    end

    Auth -->|"JWT"| Dashboard
    Dashboard --> Form & Courses & Preview & Editor & Versions & Docs

    Form -->|"POST /submissions"| SubAPI
    SubAPI -->|"refine"| LLM
    SubAPI --> Supa

    Courses --> CoursesAPI
    CoursesAPI --> Redis
    Redis -.->|"miss"| Supa

    Preview --> PreviewAPI
    PreviewAPI --> WeasyPrint

    Editor -->|"SSE"| ChatAPI
    ChatAPI --> LLM
    LLM -->|"tool calls"| AgentAPI
    AgentAPI --> Supa

    VersionsAPI --> Supa
```

| Layer | Stack |
|---|---|
| Backend | Python 3.12, FastAPI 0.138, Uvicorn |
| Frontend | Vanilla HTML/CSS/JS (no build step) |
| Database | Supabase (PostgreSQL) |
| Cache | Upstash Redis (optional, falls back to in-memory) |
| AI/LLM | OpenRouter (streaming, tool calling, fallback model retry) |
| PDF | Jinja2 + WeasyPrint (A4 layout with PES University letterhead) |
| Auth | Supabase Auth (JWT) |
| Deploy | Docker on HF Spaces, Vercel frontend proxy |
| Monitoring | Sentry SDK (optional) |

## Features

- **Course submission** with auto-parsed course codes (semester, department, credits extracted from the code itself)
- **AI refinement** that preserves all syllabus topics, only cleans and structures content
- **Full curriculum PDFs** in PES University's official A4 format with letterhead, summary tables, and course details
- **Agentic Editor** with AI assistant (SSE streaming, 35 tools, draft review, file attachments)
- **Reviewable drafts** - the agent never auto-applies changes; every edit goes through human review
- **Agent retry with fallback model** (Fibonacci backoff on 502/503, automatic model switch)
- **Chat persistence** (messages, tool calls, and tool results saved to database across sessions)
- **Dynamic specialization management** (DB-driven tracks, not hardcoded)
- **Version snapshots** with restore, revision history, and version-vs-version comparison
- **Course visibility toggle** and credit-based sorting
- **Dual cache layer** (Redis + in-memory, lazy invalidation)
- **Authentication** via Supabase Auth (JWT)
- **35 agent tools** for reading, writing, and managing curriculum data
- **49 API endpoints** across 9 route files

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd backend && fastapi dev app/main.py
```

Server at `http://127.0.0.1:8000`. API under `/api`. Frontend served from `frontend/`.

```bash
source .venv/bin/activate
pytest                              # 229 tests
python -m compileall backend/app    # also runs in CI
```

## Documentation

Full documentation is available on the **[Docs page](https://syntagma.lonelyguy.tech/docs/)** within the app, covering:

- System architecture and data flow
- Submission pipeline, refinement, preview, specializations, agent system, versioning
- All 49 API endpoints with request/response schemas
- Database schema, 12 tables, status lifecycles
- Environment variables (required and optional)
- Deployment (Docker, Vercel, HF Spaces, CI/CD)
- All 35 agent tools with descriptions

## Project Structure

```
backend/          FastAPI (Python) ASGI entrypoint at app/main.py
frontend/         Vanilla HTML/CSS/JS, no build step
tests/            29 pytest files (229 tests)
docs/             Markdown docs source (rendered as frontend surface)
```

## Screenshots

### Sign In

![Sign In - email and password authentication via Supabase Auth](assets/images/auth_page.png)

### Dashboard

![Dashboard - navigation hub linking to all surfaces](assets/images/home_page.png)

### Course Submission

![Course Submission - faculty enter course code, title, content, and references](assets/images/submit_course_page.png)

### Courses Management

![Courses Default - filterable table with semester, code, title, credits, and visibility toggle](assets/images/courses_default.png)

![Courses with Filter and Visibility Toggle - semester and visibility filters applied](assets/images/courses_filtered_visible_toggle.png)

![Delete Confirmation - confirmation dialog before archiving a course](assets/images/courses_delete_modal.png)

### PDF Preview

![Full Document Preview - complete curriculum rendered as a multi-page PDF in the browser](assets/images/preview_full_doc.png)

![Semester Preview - single semester PDF with summary tables and course details](assets/images/preview_full_sem.png)

![Single Course Preview - individual course page with syllabus, textbooks, and outcomes](assets/images/preview_single_course.png)

### Agentic Editor

![Agentic Editor - AI assistant chat, JSON fields editor, and draft review in a three-tab side panel](assets/images/editor_sample_annotated.png)

![Agentic Editor Single Course - course preview with agent chat and version controls](assets/images/editor_single_course.png)

### Version History

![Versions Default - sidebar list of curriculum snapshots with expand/collapse groups](assets/images/versions_default.png)

![Version Comparison - side-by-side diff between two version snapshots](assets/images/versions_annotated_comparision.png)

![Version Rename - inline rename form for version names and categories](assets/images/versions_rename_category.png)

![Current Document Version - live curriculum state shown as the "Current" entry](assets/images/versions_current_document.png)
