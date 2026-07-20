---
title: Syntagma
layout: default
permalink: /
---

# Syntagma

**An Agentic Curriculum Lifecycle Management System for PES University**

Syntagma is a FastAPI + static-frontend application that collects course submissions from faculty, refines them into curriculum-ready records with an LLM, renders the entire syllabus as HTML/PDF, lets an assistant agent propose and apply reviewable edits, and preserves named curriculum snapshots (versions).

It is built for a real, fast-changing syllabus: PESU revamps course content nearly every academic year, so nothing about the produced document is hardcoded. Course data, elective categorization, and specialization brackets all live in the database and are rendered dynamically.

## Live Demo

**[syntagma.lonelyguy.tech](https://syntagma.lonelyguy.tech/)** (preferred, works across browsers)

Backup: [pesucurriculum.vercel.app](https://pesucurriculum.vercel.app/)

## Quick Links

| Section | What's Inside |
|---------|---------------|
| [Architecture](/architecture/) | System design, data flow, and sequence diagrams |
| [How It Works](/how-it-works/) | Submission pipeline, refinement, preview, specializations, agent system, versioning |
| [API Reference](/api-reference/) | All 49 endpoints with request/response schemas |
| [Database Schema](/database-schema/) | 12 tables, status lifecycles, relationships |
| [Environment](/environment/) | Required and optional environment variables |
| [Deployment](/deployment/) | Docker, HF Spaces, Vercel, CI/CD |
| [Screenshots](/screenshots/) | Visual walkthrough of every surface |

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
pytest                              # all tests
python -m compileall backend/app    # also runs in CI
```
