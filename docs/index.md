---
title: PESU Curriculum Automation
permalink: /
---

# PESU Curriculum Automation

PESU Curriculum Automation is a FastAPI + static-frontend application that collects
course submissions from faculty, refines them into curriculum-ready records with an
LLM, renders the entire syllabus as HTML/PDF, lets an assistant agent propose and
apply reviewable edits, and preserves named curriculum snapshots (versions).

It is built for a real, fast-changing syllabus: PESU revamps course content nearly
every academic year, so nothing about the produced document is hardcoded. Course
data, elective categorization, and specialization brackets all live in the database
and are rendered dynamically.

## Architecture Overview

```
Faculty ─▶ Frontend (static HTML/CSS/JS) ─▶ FastAPI backend (/api)
                                                │
                              ┌─────────────────┼──────────────────┐
                              ▼                 ▼                  ▼
                        Supabase (Postgres)  OpenRouter (LLM)   WeasyPrint (PDF)
                              │
                  submissions / refined_submissions / versions / drafts / chat
```

| Layer | Location | Responsibility |
| --- | --- | --- |
| Static frontend | `frontend/` | Course entry, course management, PDF preview, live editor, version history |
| API backend | `backend/app/` | FastAPI routes, validation, refinement, previews, drafts, chat, snapshots |
| Persistence | Supabase Postgres | Raw submissions, refined courses, agent drafts, chat history, attachments, curriculum versions |
| Rendering | Jinja2 + WeasyPrint | Curriculum summary pages, course detail pages, PDF exports |
| Model provider | OpenRouter | Submission refinement and live-editor chat with tool calls |

The backend serves the frontend as static files and mounts the API under `/api`.
There is no Node build step on the frontend.

---

## Project Structure

### Backend (`backend/app/`)

| Path | Responsibility |
| --- | --- |
| `main.py` | FastAPI app, CORS, Supabase/`.env` loading, mounts `/api` routers and the static frontend |
| `api.py` | Aggregates all route routers under a single `/api` router |
| `supabase.py` | Supabase client + `first_row()` helper |
| `models/submission.py` | `CourseSubmission` (request contract) and `parse_course_code()` |
| `services/deterministic.py` | `compute_hours`, `compute_program`, `compute_course_type` from credit category |
| `services/refinement.py` | The LLM refinement pipeline (`refine`) |
| `services/curriculum.py` | Sorting, ordering, version snapshots, draft records, field updates |
| `services/diffing.py` | JSON diff, protected-field validation, patch apply/merge |
| `services/preview.py` | `build_course_preview`, `build_specialization_context` |
| `services/rendering.py` | Jinja2 environment, filters, `SEMESTER_NAMES` global |
| `services/agent_tools.py` | Agent tool definitions + `TOOLS` registry + `call_tool` |
| `services/openrouter.py` | `call()` (one-shot) and `stream_chat()` (tool-calling loop) |
| `services/schema.py` | `REQUIRED_TABLES` and `schema_status()` |
| `services/errors.py` | `database_http_exception()` |
| `services/attachments.py` | Text extraction from PDF/DOCX/XLSX/TXT |
| `services/books.py` | `parse_books()` textbook parser |
| `routes/health.py` | `GET /api/health/schema` |
| `routes/submissions.py` | `POST /api/submissions`, `POST /api/submissions/{id}/refine` |
| `routes/preview.py` | Course/HTML/PDF preview endpoints |
| `routes/refined.py` | `GET`/`PATCH` a single refined course |
| `routes/courses.py` | List + soft-delete refined courses |
| `routes/agent.py` | Draft + document-draft + tool endpoints |
| `routes/chat.py` | Chat sessions, SSE streaming, attachments, system prompt |
| `routes/versions.py` | Version CRUD, restore, previews, diffs |
| `routes/auth.py` | Supabase auth check |
| `templates/jinja_sample.html` | Single course + full document renderer |
| `templates/jinja_1_to_8.html` | Semester summary tables (1-4, 7-8) |
| `templates/jinja_sem_5_6.html` | Semester 5/6 electives + specialization tables |
| `templates/jinja_diff.html` | Structured diff renderer for drafts |

### Frontend (`frontend/`)

| Path | Purpose |
| --- | --- |
| `index.html` | Dashboard hub linking to all surfaces |
| `form/` | Raw course submission form |
| `courses/` | Refined course list with filtering and soft delete |
| `preview/` | Overall or per-semester PDF preview/download |
| `live-editor/` | Course preview, chat assistant, JSON editor, draft review, version restore |
| `versions/` | Snapshot list, preview, editor handoff |
| `auth/` | Sign in |
| `shared/` | `auth-guard.js` (redirect if no token), `supabase-client.js`, `shared.css` |

### Tests (`tests/`)

Fifteen pytest files cover deterministic mapping, refinement helpers, preview
rendering, agent diffing/protected fields/tooling, OpenRouter streaming, static
frontend routes, Supabase schema checks, and attachment extraction. The full run is
fast and runs in CI.

### Docs (`docs/`)

- `index.md` — this file
- `schema.sql` — the canonical Supabase schema (run it in the SQL editor)

### `.nottracked/`

Personal reference files (SQL dumps, PDFs, scratch notes). Never committed.

---

## How It Works

### 1. Submission Pipeline

1. Faculty submit raw course data through `frontend/form/`.
2. `POST /api/submissions` (`routes/submissions.py`) validates the payload against
   `CourseSubmission`, calls `parse_course_code()` to derive `offering_department`,
   `target_department`, `semester`, and `credit_category`, inserts into
   `submissions`, and queues a background refinement task.
3. `refine(submission_id)` (`services/refinement.py`) builds deterministic academic
   fields from `credit_category`, calls OpenRouter to extract structured prose
   (objectives, outcomes, units, books), matches prior courses for "desirable
   knowledge", and upserts a `refined_submissions` row. The submission is marked
   `refined`.
4. The course becomes visible in `/api/courses`, previews, and the live editor.

`parse_course_code()` is the single source of truth for code structure. Code format:
`UE` + `YY` (year) + `DEPT` (2) + `NUMBER` (3) + `SUFFIX`. It returns a
`ParsedCourseCode` with `semester`, `offering_dept`, `target_dept`,
`credit_category`, and `is_lateral`. The canonical parser lives in
`models/submission.py`; do not duplicate it elsewhere.

### 2. Deterministic Fields

`services/deterministic.py` computes these from `credit_category` — they are not
free-form and are protected from casual edits:

| Credit category | L | T | P | S | C | Course type |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `5` | 4 | 0 | 2 | 5 | 5 | Core Course-Lab Integrated |
| `4` | 4 | 0 | 0 | 4 | 4 | Core Course |
| `2` | 2 | 0 | 0 | 2 | 2 | Core Theory |
| `0` | 0 | 0 | 0 | 0 | 0 | Foundation Course |

All configured target departments currently map to `B. TECH`.

### 3. Preview & PDF Generation

`build_course_preview(row)` (`services/preview.py`) converts a `refined_submissions`
row into the flat dict the templates render. `services/rendering.py` builds the
Jinja2 environment with the `linkify`, `course_code_for_year` filters and the
`batch_label` / `SEMESTER_NAMES` globals.

The templates compose like this:

- `jinja_sample.html` is the entry template. It renders individual course detail
  pages and, when `show_summaries=True`, includes the summary tables.
- `jinja_1_to_8.html` renders the semester summary tables for semesters 1-4 and 7-8.
- `jinja_sem_5_6.html` renders semester 5/6 electives and the specialization
  tables. **All elective and specialization data is read from the database, not
  hardcoded** (see section 4).
- `jinja_diff.html` renders structured diffs for agent drafts.

WeasyPrint turns the rendered HTML into PDF for the `/preview/pdf` and
`/preview/semester/{sem}/pdf` endpoints.

Course ordering within a semester is set by `course_sort_key` in
`services/curriculum.py`: courses sort by credits descending (5 before 4 before 2
before 0), then by the explicit `SOURCE_ORDER` position (or the `elective_order`
suffix rule for semesters 5/6), then by database id. Courses with `visible = false`
are excluded from all rendered output.

### 4. Specialization System (dynamic)

Specialization brackets and elective membership are fully data-driven.

**Tables**

- `specialization_definitions` — one row per track:
  `id, semester, letter (A/B/C…), name, key (SCC/MIDS/CSCS), academic_year`.
- `course_specialization_assignments` — one row per (course, track) membership:
  `id, refined_id, specialization_id`.
- `refined_submissions.is_elective` — boolean flag marking a course as an elective.

**How the template renders it**

`build_specialization_context()` loads all track definitions and all assignments and
passes them to the template as `specializations` and `specialization_assignments`.
`jinja_sem_5_6.html` then:

- Excludes `is_elective` courses from the regular semester table and totals.
- Splits electives into the `Elective-I/II/III/IV` tables by their code suffix
  (`AA`/`BA` → group A, `AB`/`BB` → group B). This grouping follows the university
  course-code convention, which is stable.
- Renders the "ELECTIVES TO BE OPTED FOR SPECIALIZATION" table by joining
  `specializations` to `course_specialization_assignments` and printing each
  assigned course code (year-adjusted via `course_code_for_year`).
- Uses the course's **actual** hours/credits (no hardcoded `4/0/0/4/4` override).

A course may belong to multiple specialization tracks — that is expected and handled
by multiple assignment rows.

**Agent tooling** (see section 6) lets the agent create tracks (`define_specialization`),
list them (`list_specializations`), and categorize electives
(`assign_elective_to_tracks`, `get_course_assignments`, `remove_elective_from_tracks`).

**Seeding / migration**

`.nottracked/migrate_specializations.sql` seeds the current SCC/MIDS/CSCS tracks for
semesters 5 and 6 and backfills `is_elective` flags and assignments from the legacy
hardcoded lists. Run it once in the Supabase SQL editor after the new tables exist.
It is idempotent.

### 5. Live Editor

The live editor (`frontend/live-editor/`) is the main working surface. It has three
tabs:

- **Chat** — streams the assistant via SSE. The assistant calls tools, can create
  drafts, and never applies changes itself.
- **Fields** — raw JSON editor for direct edits + "Create Draft" / "Save".
- **Review** — loads a document draft, shows the diff, and applies it.

The chat panel can be expanded with the toolbar toggle (it widens the side pane and
shrinks the preview). The preview `<iframe>` shows either a single course or the full
document.

### 6. Agent System

The agent is a tool-calling LLM loop (`openrouter.stream_chat`). It receives a system
prompt (`chat.py:chat_system_prompt`) that instructs it to prefer granular read
tools, create drafts for changes, and never apply them.

**Tools** (`services/agent_tools.py`, registered in `TOOLS`):

*Read*
- `get_current_course_json` — full template-ready course JSON
- `get_course_codes` — lightweight IDs (refined_id, code, title, semester)
- `get_course_syllabus` — units, objectives, course_outcomes
- `get_course_textbooks` — text_books, reference_books
- `get_course_deterministic` — protected fields (read-only context)
- `get_course_lab` — lab experiments, tools/languages
- `get_course_fields` — arbitrary field subset
- `get_curriculum_json` — full curriculum, optionally by semester
- `list_courses` — course IDs/titles
- `diff_course_json` — compare two course JSONs
- `get_course_draft` / `get_document_draft` — read staged drafts
- `get_course_assignments` — which specialization tracks a course belongs to
- `list_specializations` — list track definitions
- `get_attachment_text` — read uploaded chat attachments
- `fetch_url` / `web_search` — external context

*Write (always create reviewable drafts, never apply)*
- `create_course_draft` — one course
- `create_document_draft` — multiple courses
- `assign_elective_to_tracks` — categorize an elective
- `remove_elective_from_tracks` — remove a course from tracks
- `define_specialization` — create a track
- `update_deterministic_fields` — **the only** way to change protected fields;
  produces a `blocked` draft that requires explicit user approval
- `create_report` / `create_curriculum_version` / `signal_done`

**Protected fields.** `diffing.PROTECTED_FIELDS` = `program, lecture_hours,
tutorial_hours, practical_hours, self_study, credits, course_type`. Drafts that
change them are blocked (`validate_draft`). `update_deterministic_fields` is the
intended, user-confirmed path around that block.

**Draft lifecycle.** `curriculum.draft_record()` builds base/proposed JSON, a JSON
patch, and a diff summary. On apply (`agent.py`), it writes `course_revision_history`,
updates the refined row, and snapshots a version.

### 7. Versioning

`GET/POST /api/versions` create named snapshots of the whole curriculum
(`create_version_snapshot` copies every active `refined_submissions` into
`finalized_submissions` pinned to a `curriculum_versions` row). `restore` overwrites
current refined data from a snapshot, archives courses absent from the snapshot, and
writes revision history. The versions page lists snapshots, previews them (or a diff
vs. current), and hands off to the editor.

---

## API Reference

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/health/schema` | GET | Verify required Supabase tables |
| `/api/submissions` | POST | Store a raw submission, queue refinement |
| `/api/submissions/{id}/refine` | POST | Manually refine a submission |
| `/api/refined/{refined_id}` | GET | Read template-ready course fields |
| `/api/refined/{refined_id}` | PATCH | Update editable refined fields |
| `/api/courses` | GET | List active refined courses |
| `/api/courses/{refined_id}` | DELETE | Archive a refined course |
| `/api/preview/course/{refined_id}` | GET | Render one course as HTML |
| `/api/preview/html` | GET | Render the full curriculum as HTML |
| `/api/preview/pdf` | GET | Render the full curriculum as PDF |
| `/api/preview/semester/{sem}/pdf` | GET | Render one semester as PDF |
| `/api/versions` | GET, POST | List / create curriculum snapshots |
| `/api/versions/{version_id}` | GET | Snapshot + its courses |
| `/api/versions/{version_id}/restore` | POST | Restore a saved snapshot |
| `/api/versions/{version_id}/preview` | GET | Snapshot HTML (or `?diff=true` vs current) |
| `/api/agent/drafts` | GET, POST | List / create reviewable course drafts |
| `/api/agent/drafts/{id}` | GET | One draft with base/proposed JSON |
| `/api/agent/drafts/{id}/apply` | POST | Apply a proposed draft |
| `/api/agent/drafts/{id}/preview` | GET | Render diff/proposed course as HTML |
| `/api/agent/document-drafts` | GET, POST | List / create multi-course drafts |
| `/api/agent/document-drafts/{id}` | GET | Document draft + linked course drafts |
| `/api/agent/document-drafts/{id}/apply` | POST | Apply all sub-drafts |
| `/api/agent/document-drafts/{id}/preview` | GET | Render document diff/proposed HTML |
| `/api/agent/tools` | GET | List agent tool schemas |
| `/api/agent/tools/{name}` | POST | Call an agent tool directly |
| `/api/chat/sessions` | GET, POST | Manage chat sessions |
| `/api/chat/sessions/{id}/messages` | GET, POST | Read / stream chat (SSE) |
| `/api/chat/sessions/{id}/attachments` | POST | Upload files for chat context |
| `/api/chat/sessions/{id}/attachments/{attachment_id}/download` | GET | Download an attachment |
| `/api/auth/check` | GET | Verify the bearer token |

All preview/diff/version endpoints accept `?curriculum_year=` to pin the batch year.

---

## Database Schema

Run `docs/schema.sql` in the Supabase SQL editor. Required tables:

`submissions`, `refined_submissions`, `curriculum_versions`, `finalized_submissions`,
`agent_drafts`, `agent_document_drafts`, `course_revision_history`, `chat_sessions`,
`chat_messages`, `chat_attachments`, `specialization_definitions`,
`course_specialization_assignments`.

Key columns on `refined_submissions`: `course_code, course_title, semester,
credit_category, program, lecture_hours, tutorial_hours, practical_hours, self_study,
credits, course_type, is_elective, visible, units (jsonb), objectives/text_books/…
(arrays), status`.

`visible` (default `true`) controls whether a course renders in preview/PDF output.
Toggle it from the course management page. Hidden courses stay in the database and
remain editable but are excluded from every rendered document.

Verify with `GET /api/health/schema`.

---

## Environment Variables

Required backend (`/api` server, loaded from repo-root `.env`):

- `SUPABASE_URL`, `SUPABASE_KEY`
- `OPENROUTER_URL`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`

Optional:

- `CURRICULUM_YEAR` — the active batch label (e.g. `2025-26`)
- `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_RELEASE`

The frontend uses the public Supabase anon key directly in `shared/supabase-client.js`.

---

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd backend
fastapi dev app/main.py
```

Server at `http://127.0.0.1:8000`. API under `/api`. Frontend served from `frontend/`.

```bash
source .venv/bin/activate
pytest                              # all tests
python -m compileall backend/app    # also runs in CI
```

---

## Deployment

Docker image runs `uvicorn app.main:app --host 0.0.0.0 --port 7860` (HF Space).
`.github/workflows/sync-to-hub.yml` syncs `main` to the HF Space. The static
frontend is also deployable; `frontend/vercel.json` rewrites `/api/*` to the backend.

---

## For Teammates: Specialization Pipeline

This is the active work area. The templates, schema, and agent tools are already in
place. Your task is the **elective detection + AI categorization pipeline**.

### What already exists (do not rebuild)

- `refined_submissions.is_elective` flag and the `specialization_*` tables.
- `build_specialization_context()` feeds the templates; they render correctly once
  assignments exist.
- Agent tools `define_specialization`, `list_specializations`,
  `assign_elective_to_tracks`, `get_course_assignments`, `remove_elective_from_tracks`.
- `.nottracked/migrate_specializations.sql` shows the exact legacy groupings to
  backfill existing data.

### What you build

A pipeline that runs after refinement finishes for a course:

1. Detect: is the new `refined_submissions` row an elective? Heuristic: course code
   contains `AA/AB/BA/BB` and semester is 5 or 6 (mirror the migration's rule), or
   simply check the new `is_elective` flag once set.
2. Gather context: call `list_specializations` (or query
   `specialization_definitions` for the course's semester) to get the track names
   and descriptions.
3. Analyze: pass the elective's title + content + the track definitions to the LLM
   using `openrouter.call(system, user)` (see `services/openrouter.py` — that is the
   integrated client; do not add a new model integration). Ask it to return which
   `specialization_id`s the course fits and a short reasoning per track.
4. Insert: call `assign_elective_to_tracks` (or insert into
   `course_specialization_assignments` directly) for each track. Always include the
   reasoning in logs.
5. Guardrails: if confidence is low or the model returns a track that does not exist,
   surface it for human confirmation rather than guessing. The goal is zero
   hallucinated placements.

### Trigger options

- Hook into `refine()` in `services/refinement.py` after the upsert, or
- A periodic job that scans for `refined_submissions` rows with `is_elective` true and
  no `course_specialization_assignments` entry.

Either is fine; keep it isolated so it does not block the submission response.

### How to add an agent tool

1. Write a `_name(arguments)` handler in `services/agent_tools.py` (raise `ValueError`
   for bad input; return a JSON-serializable dict).
2. Register it in the `TOOLS` dict with an `AgentTool(name, description, parameters, handler)`.
3. Add a test in `tests/test_agent_tools.py` asserting the schema exists and bad input
   fails.

### How to modify a template

Templates live in `backend/app/templates/`. They receive context built in
`services/preview.py` + the route. Prefer adding data to `build_course_preview` /
`build_specialization_context` over hardcoding anything in HTML. The `do` extension
is enabled, so mutable {% raw %}`{% set x = [] %}{% do x.append(...) %}`{% endraw %} works. Always read
list context through `|default([])` so a missing key never crashes rendering.
