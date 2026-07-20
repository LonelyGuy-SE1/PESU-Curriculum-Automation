---
title: Architecture
layout: default
permalink: /architecture/
---

# Architecture Overview

## System Architecture

```mermaid
flowchart TB
    subgraph Frontend
        Dashboard[Dashboard /]
        Form[Submit Course /form/]
        Courses[Courses /courses/]
        Preview[Preview /preview/]
        Editor[Agentic Editor /live-editor/]
        Versions[Version History /versions/]
        Auth[Sign In /auth/]
    end

    subgraph Backend["FastAPI Backend (/api)"]
        Health[Health Check]
        Submissions[Submissions]
        PreviewAPI[Preview]
        Refined[Refined]
        CoursesAPI[Courses]
        AgentAPI[Agent]
        ChatAPI[Chat]
        VersionsAPI[Versions]
    end

    subgraph External
        LLM[OpenRouter LLM]
        Supa[(Supabase Postgres)]
        Redis[(Redis / Memory Cache)]
        WeasyPrint[WeasyPrint PDF]
    end

    Dashboard --> Form & Courses & Preview & Editor & Versions
    Auth -->|"JWT guard"| Dashboard
    Form -->|"POST /api/submissions"| Submissions
    Submissions -->|"refine()"| LLM
    Submissions --> Supa
    Editor -->|"SSE stream"| ChatAPI
    ChatAPI -->|"tool calls"| AgentAPI
    AgentAPI --> Supa
    PreviewAPI --> WeasyPrint
    CoursesAPI --> Redis
    VersionsAPI --> Supa
```

## Data Flow Sequences

### Submission Flow

```mermaid
sequenceDiagram
    participant F as Faculty
    participant FE as Form Page
    participant API as FastAPI
    participant DB as Supabase
    participant LLM as OpenRouter

    F->>FE: Fill form, submit
    FE->>API: POST /api/submissions
    API->>API: parse_course_code()
    API->>DB: INSERT INTO submissions
    API-->>FE: 200 { submission }
    API->>API: Background: refine(submission_id)
    API->>DB: INSERT INTO refined_submissions
    API->>LLM: Extract structured content
    LLM-->>API: Objectives, outcomes, units, books
    API->>DB: UPDATE refined_submissions
```

### Chat & Tool Calling

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Editor UI
    participant API as Chat API
    participant LLM as OpenRouter
    participant Tools as Agent Tools
    participant DB as Supabase

    U->>FE: Type message + Send
    FE->>API: POST /chat/sessions/{id}/messages
    API->>DB: Save user message
    API->>LLM: System prompt + user message
    loop Tool-calling loop (max 3 rounds)
        LLM-->>API: tool_call event
        API->>DB: Save tool_call message
        API-->>FE: SSE event: tool_call
        API->>Tools: call_tool(name, args)
        Tools-->>API: result
        API->>DB: Save tool_result message
        API-->>FE: SSE event: tool_result
        API->>LLM: Tool result
    end
    LLM-->>API: Final text response
    API-->>FE: SSE event: token (streamed)
    API->>DB: Save assistant message
    API-->>FE: SSE event: done
```

### Draft Lifecycle

```mermaid
sequenceDiagram
    participant U as User
    participant LLM as Agent
    participant API as API
    participant DB as Supabase

    U->>LLM: "Update syllabus for CS301"
    LLM->>API: create_course_draft(refined_id, fields)
    API->>DB: INSERT INTO agent_drafts (status: proposed)
    LLM-->>U: "I've proposed changes for review"
    U->>API: Review tab -> Load draft
    API->>DB: SELECT agent_drafts
    API-->>U: Diff view (base vs proposed)
    U->>API: POST /agent/drafts/{id}/apply
    API->>API: validate_draft()
    API->>DB: UPDATE refined_submissions
    API->>DB: INSERT INTO course_revision_history
    API->>DB: INSERT INTO curriculum_versions
    API-->>U: Applied + version snapshot
```

## Layer Responsibilities

| Layer | Location | Responsibility |
|-------|----------|----------------|
| Static frontend | `frontend/` | Course entry, course management, PDF preview, agentic editor, version history |
| API backend | `backend/app/` | FastAPI routes, validation, refinement, previews, drafts, chat, snapshots |
| Persistence | Supabase Postgres | Raw submissions, refined courses, agent drafts, chat history, attachments, curriculum versions |
| Cache | Redis + in-memory | Course lists, version lists, PDFs, with lazy invalidation |
| Rendering | Jinja2 + WeasyPrint | Curriculum summary pages, course detail pages, PDF exports |
| Model provider | OpenRouter | Submission refinement and live-editor chat with tool calls + fallback model retry |

The backend serves the frontend as static files and mounts the API under `/api`. There is no Node build step on the frontend.

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend framework | FastAPI 0.138 + Uvicorn | ASGI server, routing, validation |
| Language | Python 3.12 | Runtime |
| Frontend | Vanilla HTML/CSS/JS | No build step, served as static files |
| Database | Supabase (PostgreSQL) | Persistent storage for all data |
| Cache | Upstash Redis (optional) | Serverless Redis; falls back to in-memory dict |
| LLM provider | OpenRouter | Streaming + tool calling, fallback model retry |
| PDF engine | WeasyPrint | A4 curriculum PDFs from Jinja2 HTML |
| Templating | Jinja2 | Curriculum layout, course pages, diffs |
| HTTP client | httpx | Async requests to OpenRouter and external URLs |
| Spreadsheet parsing | openpyxl | Reading uploaded .xlsx files for text extraction |
| Markdown rendering | marked.js (CDN) | Agent chat message rendering in browser |
| HTML sanitization | DOMPurify (CDN) | Sanitizing agent-generated HTML |
| PDF text extraction | poppler-utils (pdftotext) | Extracting text from uploaded PDF attachments |
| Auth | Supabase Auth (JWT) | Browser-based authentication |
| Error tracking | Sentry SDK (optional) | Production error monitoring |
| Deployment | Docker on HF Spaces | Backend at port 7860 |
| Frontend deploy | Vercel | Static hosting with `/api` rewrite to backend |

## Project Structure

### Backend (`backend/app/`)

| Path | Responsibility |
|------|----------------|
| `main.py` | FastAPI app, CORS, Supabase/`.env` loading, mounts `/api` routers and the static frontend |
| `api.py` | Aggregates all route routers under a single `/api` router |
| `supabase.py` | Supabase client + `first_row()` helper |
| `cache.py` | Dual cache (Redis + in-memory), lazy invalidation, prefix-based deletion |
| `models/submission.py` | `CourseSubmission` (request contract) and `parse_course_code()` |
| `services/deterministic.py` | `compute_hours`, `compute_program`, `compute_course_type` from credit category |
| `services/refinement.py` | The LLM refinement pipeline (`refine`) |
| `services/curriculum.py` | Sorting, ordering, version snapshots, draft records, field updates |
| `services/diffing.py` | JSON diff, protected-field validation, patch apply/merge |
| `services/preview.py` | `build_course_preview`, `build_specialization_context` |
| `services/rendering.py` | Jinja2 environment, filters, `SEMESTER_NAMES` global |
| `services/agent_tools.py` | Agent tool definitions + `TOOLS` registry (35 tools) + `call_tool` |
| `services/openrouter.py` | `call()` (one-shot), `stream_chat()` (tool-calling loop), fallback model retry |
| `services/schema.py` | `REQUIRED_TABLES` and `schema_status()` |
| `services/errors.py` | `database_http_exception()` |
| `services/attachments.py` | Text extraction from PDF/DOCX/XLSX/TXT |
| `services/books.py` | `parse_books()` textbook parser |
| `routes/health.py` | `GET /api/health/schema` |
| `routes/submissions.py` | `POST /api/submissions`, `POST /api/submissions/{id}/refine` |
| `routes/preview.py` | Course/HTML/PDF preview endpoints (8 endpoints) |
| `routes/refined.py` | `GET`/`PATCH` a single refined course |
| `routes/courses.py` | List + toggle visibility + soft-delete refined courses |
| `routes/agent.py` | Draft + document-draft + tool endpoints (13 endpoints) |
| `routes/chat.py` | Chat sessions, SSE streaming, attachments, system prompt |
| `routes/versions.py` | Version CRUD, restore, previews, diffs (10 endpoints) |
| `templates/jinja_sample.html` | Single course + full document renderer + title page |
| `templates/jinja_program.html` | Program-level title page (large seal) + PEOs/POs |
| `templates/jinja_1_to_8.html` | Semester summary tables (1-4, 7-8) |
| `templates/jinja_sem_5_6.html` | Semester 5/6 electives + specialization tables |
| `templates/jinja_diff.html` | Structured diff renderer for drafts |

### Frontend (`frontend/`)

| Path | Purpose |
|------|---------|
| `index.html` | Dashboard hub linking to all surfaces |
| `form/` | Raw course submission form with course code parsing |
| `courses/` | Refined course list with filtering, visibility toggle, soft delete |
| `preview/` | Overall or per-semester PDF preview/download |
| `live-editor/` | Agentic Editor: course preview, chat assistant, JSON editor, draft review, version restore |
| `versions/` | Snapshot list, preview, comparison, editor handoff |
| `auth/` | Sign in (Supabase Auth) |
| `shared/` | `auth-guard.js`, `supabase-client.js`, `shared.css`, `dialog.js` |

### Tests (`tests/`)

29 pytest files covering deterministic mapping, refinement helpers, preview rendering, agent diffing/protected fields/tooling, OpenRouter streaming, static frontend routes, Supabase schema checks, attachment extraction, cache invalidation, and benchmark tests. The full run is fast and runs in CI.

### Docs (`docs/`)

- `index.md` -- this file (GitHub Pages site)
- `schema.sql` -- the canonical Supabase schema (run it in the SQL editor)

### `.nottracked/`

Personal reference files (SQL dumps, PDFs, scratch notes). Never committed.