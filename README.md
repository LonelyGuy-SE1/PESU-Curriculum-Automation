---
title: Curriculum Backend
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# PESU Curriculum Automation

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
[![Docs](https://img.shields.io/badge/docs-Pages-blue?style=flat-square&logo=github&logoColor=white)](https://lonelyguy-se1.github.io/PESU-Curriculum-Automation/)

</div>

Automate PES University's B.Tech curriculum management: faculty submit raw course content, the system refines it via AI, and admins review, edit, and export the full curriculum as official A4 PDFs.

## Live Demo

**[pesucurriculum.lonelyguy.tech](https://pesucurriculum.lonelyguy.tech/)** (preferred, works across browsers)

Backup: [HF Space](https://huggingface.co/spaces/Lonelyguyse1/Curriculum-Backend) (may have compatibility issues on some browsers)

## Architecture

```mermaid
flowchart LR
    F[Faculty] -->|submits raw content| Form[Form]
    Form -->|POST /api/submissions| API[FastAPI]
    API -->|refine| LLM[OpenRouter LLM]
    API -->|store| DB[(Supabase Postgres)]
    API -.->|cache| Cache[(Redis / Memory)]

    Admin[Admin] --> Editor[Agentic Editor]
    Editor -->|chat + tools| API
    Editor -->|review drafts| API
    API -->|render| Jinja2[Jinja2 Templates]
    Jinja2 -->|PDF| WeasyPrint[WeasyPrint]
    WeasyPrint --> PDF[Curriculum PDF]
```

| Layer | Stack |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Frontend | Vanilla HTML/CSS/JS (no build step) |
| Database | Supabase (PostgreSQL) |
| Cache | Upstash Redis (optional, falls back to in-memory) |
| AI/LLM | OpenRouter (streaming, tool calling, fallback model retry) |
| PDF | Jinja2 + WeasyPrint (A4 layout) |
| Auth | Supabase Auth (JWT) |
| Deploy | Docker on HF Spaces, Vercel frontend proxy |
| Monitoring | Sentry (optional, error tracking) |

## Features

- **Course submission** with auto-parsed course codes (semester, department, credits extracted automatically)
- **AI refinement** that preserves all syllabus topics, only cleans and structures content
- **Full curriculum PDFs** in PES University's official A4 format with letterhead
- **Agentic Editor** with AI assistant (SSE streaming, 35 tools, draft review, attachments)
- **Reviewable drafts** (agent never auto-applies changes)
- **Agent retry with fallback model** (fibonacci backoff on 502/503, automatic model switch)
- **Chat persistence** (messages, tool calls, and results saved to database)
- **Dynamic specialization management** (DB-driven tracks, not hardcoded)
- **Version snapshots** with restore, revision history, and version-vs-version comparison
- **Course visibility toggle** and credit-based sorting
- **Dual cache layer** (Redis + in-memory, lazy invalidation)
- **Authentication** via Supabase Auth

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd backend && fastapi dev app/main.py
```

Server at `http://127.0.0.1:8000`. API under `/api`. Frontend served from `frontend/`.

## Agent Tools

The Agentic Editor includes an AI assistant with 35 tools for reading, writing, and managing curriculum data:

| Category | Tools | Description |
|---|---|---|
| **Read (course)** | `get_current_course_json`, `get_course_codes`, `get_course_syllabus`, `get_course_textbooks`, `get_course_deterministic`, `get_course_lab`, `get_course_fields`, `batch_read_courses`, `get_curriculum_json`, `list_courses`, `get_curriculum_stats` | Browse courses, read specific fields, load full curriculum, compute aggregate statistics |
| **Read (comparison)** | `diff_course_json`, `get_course_draft`, `get_document_draft`, `get_version`, `diff_versions` | Compare course JSONs, read staged drafts, inspect version snapshots |
| **Read (external)** | `get_course_assignments`, `list_specializations`, `get_attachment_text`, `fetch_url`, `web_search` | Specialization tracks, uploaded files, web content |
| **Write (drafts)** | `create_course_draft`, `update_agent_draft`, `create_document_draft` | Propose changes for human review; update existing drafts instead of duplicating |
| **Write (direct)** | `create_refined_course` | Create new courses directly (for brand-new courses only) |
| **Write (specialization)** | `define_specialization`, `assign_elective_to_tracks`, `remove_elective_from_tracks`, `categorize_elective` | Manage elective tracks and AI-powered categorization |
| **Write (protected)** | `update_deterministic_fields` | The only way to change protected fields; produces a blocked draft |
| **Generate** | `create_report`, `create_spreadsheet`, `create_curriculum_version` | Markdown/PDF reports, CSV/Excel exports, version snapshots |
| **Control** | `signal_done` | Signal task completion with a summary |

Full tool schemas and documentation: [PESU Curriculum Docs](https://lonelyguy-se1.github.io/PESU-Curriculum-Automation/)

## Documentation

Full documentation is on the [GitHub Pages site](https://lonelyguy-se1.github.io/PESU-Curriculum-Automation/):

- [API Reference](https://lonelyguy-se1.github.io/PESU-Curriculum-Automation/#api-reference) -- all 49 endpoints
- [Database Schema](https://lonelyguy-se1.github.io/PESU-Curriculum-Automation/#database-schema) -- 12 tables
- [Local Development](https://lonelyguy-se1.github.io/PESU-Curriculum-Automation/#local-development) -- setup and run
- [Deployment](https://lonelyguy-se1.github.io/PESU-Curriculum-Automation/#deployment) -- Docker, Vercel, HF Spaces
- [Environment Variables](https://lonelyguy-se1.github.io/PESU-Curriculum-Automation/#environment-variables) -- required and optional
- [How It Works](https://lonelyguy-se1.github.io/PESU-Curriculum-Automation/#how-it-works) -- submission pipeline, refinement, preview, specializations, agent system, versioning

## Project Structure

See [docs/index.md#project-structure](https://lonelyguy-se1.github.io/PESU-Curriculum-Automation/#project-structure) for the full breakdown.
