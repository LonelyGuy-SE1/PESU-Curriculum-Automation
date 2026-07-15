---
title: Curriculum Backend
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# PESU Curriculum Automation

![Python](https://img.shields.io/badge/python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/fastapi-0.138-009688?style=flat-square&logo=fastapi&logoColor=white)
![Supabase](https://img.shields.io/badge/supabase-postgres-3FCF8E?style=flat-square&logo=supabase&logoColor=white)
![OpenRouter](https://img.shields.io/badge/openrouter--llm-6366F1?style=flat-square&logo=openai&logoColor=white)
![WeasyPrint](https://img.shields.io/badge/weasyprint-pdf-E64B1A?style=flat-square&logo=markdown&logoColor=white)
![CI](https://img.shields.io/badge/CI-passing-brightgreen?style=flat-square&logo=githubactions&logoColor=white)
![Tests](https://img.shields.io/badge/tests-87-green?style=flat-square&logo=pytest&logoColor=white)
![Sentry](https://img.shields.io/badge/sentry--sdk-2.63-362D59?style=flat-square&logo=sentry&logoColor=white)
![HF Space](https://img.shields.io/badge/deploy-HF%20Spaces-yellow?style=flat-square&logo=huggingface&logoColor=white)
![Vercel](https://img.shields.io/badge/frontend-Vercel-black?style=flat-square&logo=vercel&logoColor=white)

Automate PES University's B.Tech curriculum management: faculty submit raw course content, the system refines it via AI, and admins review, edit, and export the full curriculum as official A4 PDFs.

## Live Demo

**[pesucurriculum.vercel.app](https://pesucurriculum.vercel.app/)** (preferred, works across browsers)

Backup: [HF Space](https://huggingface.co/spaces/Lonelyguyse1/Curriculum-Backend) (may have compatibility issues on some browsers)

## Architecture

```mermaid
flowchart LR
    F[Faculty] -->|submits raw content| Form[Form]
    Form -->|POST /api/submissions| API[FastAPI]
    API -->|refine| LLM[OpenRouter LLM]
    API -->|store| DB[(Supabase Postgres)]

    Admin[Admin] --> Editor[Live Editor]
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
| AI/LLM | OpenRouter (streaming + tool calling) |
| PDF | Jinja2 + WeasyPrint (A4 layout) |
| Auth | Supabase Auth (JWT) |
| Deploy | Docker on HF Spaces, Vercel frontend proxy |
| Monitoring | Sentry (optional, error tracking) |

## Features

- **Course submission** with auto-parsed course codes (semester, department, credits extracted automatically)
- **AI refinement** that preserves all syllabus topics, only cleans and structures content
- **Full curriculum PDFs** in PES University's official A4 format with letterhead
- **Live editor** with AI assistant (SSE streaming, 32 tools, draft review)
- **Reviewable drafts** (agent never auto-applies changes)
- **Dynamic specialization management** (DB-driven tracks, not hardcoded)
- **Version snapshots** with restore and revision history
- **Course visibility toggle** and credit-based sorting
- **Authentication** via Supabase Auth

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd backend && fastapi dev app/main.py
```

Server at `http://127.0.0.1:8000`. API under `/api`. Frontend served from `frontend/`.

## Documentation

Full documentation is in [docs/index.md](docs/index.md):

- [API Reference](docs/index.md#api-reference) -- all 35 endpoints
- [Database Schema](docs/schema.sql) -- 12 tables
- [Local Development](docs/index.md#local-development) -- setup and run
- [Deployment](docs/index.md#deployment) -- Docker, Vercel, HF Spaces
- [Environment Variables](docs/index.md#environment-variables) -- required and optional
- [How It Works](docs/index.md#how-it-works) -- submission pipeline, refinement, preview, specializations, agent system, versioning

## Project Structure

See [docs/index.md#project-structure](docs/index.md#project-structure) for the full breakdown.
