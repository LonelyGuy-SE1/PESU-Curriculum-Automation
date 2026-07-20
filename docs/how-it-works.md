---
layout: default
title: How It Works
permalink: /how-it-works/
---

# How It Works

## 1. Submission Pipeline

1. Faculty submit raw course data through `frontend/form/`.
2. `POST /api/submissions` (`routes/submissions.py`) validates the payload against `CourseSubmission`, calls `parse_course_code()` to derive `offering_department`, `target_department`, `semester`, and `credit_category`, inserts into `submissions`, and queues a background refinement task.
3. `refine(submission_id)` (`services/refinement.py`) builds deterministic academic fields from `credit_category`, calls OpenRouter to extract structured prose (objectives, outcomes, units, books), matches prior courses for "desirable knowledge", and upserts a `refined_submissions` row. The submission is marked `refined`.
4. The course becomes visible in `/api/courses`, previews, and the Agentic Editor.

**Course code encoding:** `UE` + `YY` (2-digit year) + `DEPT` (2-letter department) + `NUMBER` (3-digit number) + `SUFFIX`. The 3-digit number encodes:
- **Tens digit** = credits (0/2/4/5)
- **Hundreds digit** = semester group
- **Suffix** A/B = odd/even semester parity

`parse_course_code()` is the single source of truth for code structure. It returns a `ParsedCourseCode` with `semester`, `offering_dept`, `target_dept`, `credit_category`, and `is_lateral`. The canonical parser lives in `models/submission.py`; do not duplicate it elsewhere.

## 2. Deterministic Fields

`services/deterministic.py` computes these from `credit_category` -- they are not free-form and are protected from casual edits:

| Credit category | L | T | P | S | C | Course type |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `5` | 4 | 0 | 2 | 5 | 5 | Core Course-Lab Integrated |
| `4` | 4 | 0 | 0 | 4 | 4 | Core Course |
| `2` | 2 | 0 | 0 | 2 | 2 | Core Theory |
| `0` | 0 | 0 | 0 | 0 | 0 | Foundation Course |

All configured target departments currently map to `B. TECH`.

**Protected fields** (`diffing.py`): `program, lecture_hours, tutorial_hours, practical_hours, self_study, credits, course_type`. Drafts that change them are blocked (`validate_draft`). `update_deterministic_fields` is the intended, user-confirmed path around that block.

## 3. Preview & PDF Generation

`build_course_preview(row)` (`services/preview.py`) converts a `refined_submissions` row into the flat dict the templates render. `services/rendering.py` builds the Jinja2 environment with the `linkify`, `course_code_for_year` filters and the `batch_label` / `SEMESTER_NAMES` globals.

The templates compose like this:

- `jinja_program.html` is the program-level template. It renders the title page (large PES University seal, program name, academic year) and the PEOs/POs page.
- `jinja_sample.html` is the entry template. It renders individual course detail pages and, when `show_summaries=True`, includes the summary tables. A conditional `show_thank_you` flag controls the "Thank You" page (skipped in single course/draft/version previews).
- `jinja_1_to_8.html` renders the semester summary tables for semesters 1-4 and 7-8.
- `jinja_sem_5_6.html` renders semester 5/6 electives and the specialization tables. **All elective and specialization data is read from the database, not hardcoded** (see section 4).
- `jinja_diff.html` renders structured diffs for agent drafts.

WeasyPrint turns the rendered HTML into PDF for the `/preview/pdf` and `/preview/semester/{sem}/pdf` endpoints.

**PDF preload:** PDFs are preloaded into an invisible iframe on page load for faster perceived rendering. Course-specific PDFs use the endpoint `/api/preview/course/{refined_id}/pdf`.

**Caching:** Course PDFs are cached for 60 seconds. Course lists and version lists are cached for 180 seconds. Cache is invalidated lazily on mutations (keys deleted, next read misses cache, fetches fresh from Supabase, re-caches).

Course ordering within a semester is set by `course_sort_key` in `services/curriculum.py`: courses sort by credits descending (5 before 4 before 2 before 0), then by the explicit `SOURCE_ORDER` position (or the `elective_order` suffix rule for semesters 5/6), then by database id. Courses with `visible = false` are excluded from all rendered output.

![PDF Preview - Full Document](assets/images/preview_full_doc.png)
![PDF Preview - Semester](assets/images/preview_full_sem.png)
![PDF Preview - Single Course](assets/images/preview_single_course.png)

## 4. Specialization System (dynamic)

Specialization brackets and elective membership are fully data-driven.

**Tables**

- `specialization_definitions` -- one row per track: `id, semester, letter (A/B/C...), name, key (SCC/MIDS/CSCS), academic_year`.
- `course_specialization_assignments` -- one row per (course, track) membership: `id, refined_id, specialization_id`.
- `refined_submissions.is_elective` -- boolean flag marking a course as an elective.

**How the template renders it**

`build_specialization_context()` loads all track definitions and all assignments and passes them to the template as `specializations` and `specialization_assignments`. `jinja_sem_5_6.html` then:

- Excludes `is_elective` courses from the regular semester table and totals.
- Splits electives into the `Elective-I/II/III/IV` tables by their code suffix (`AA`/`BA` -> group A, `AB`/`BB` -> group B). This grouping follows the university course-code convention, which is stable.
- Renders the "ELECTIVES TO BE OPTED FOR SPECIALIZATION" table by joining `specializations` to `course_specialization_assignments` and printing each assigned course code (year-adjusted via `course_code_for_year`).
- Uses the course's **actual** hours/credits (no hardcoded `4/0/0/4/4` override).

A course may belong to multiple specialization tracks -- that is expected and handled by multiple assignment rows.

**Agent tooling** (see section 6) lets the agent create tracks (`define_specialization`), list them (`list_specializations`), and categorize electives (`assign_elective_to_tracks`, `get_course_assignments`, `remove_elective_from_tracks`, `categorize_elective`).

**Seeding / migration**

`.nottracked/migrate_specializations.sql` seeds the current SCC/MIDS/CSCS tracks for semesters 5 and 6 and backfills `is_elective` flags and assignments from the legacy hardcoded lists. Run it once in the Supabase SQL editor after the new tables exist. It is idempotent.

![Courses Management - Default](assets/images/courses_default.png)
![Courses Management - Filtered](assets/images/courses_filtered_visible_toggle.png)
![Courses Management - Delete Modal](assets/images/courses_delete_modal.png)

## 5. Agentic Editor

The Agentic Editor (`frontend/live-editor/`) is the main working surface. It has three tabs:

**Agent tab** -- streams the assistant via SSE. The assistant calls 35 tools, can create drafts, generate reports, search the web, and never applies changes itself. Chat messages are persisted to the database including tool calls and results. Thread management supports multiple chat sessions per course with rename/delete.

**Fields tab** -- raw JSON editor for direct edits + "Propose Changes" / "Save". "Propose Changes" creates a reviewable draft. "Save" directly updates the refined course (only for non-protected fields).

**Review tab** -- loads pending drafts (agent-created, course, or document drafts), shows the diff, and applies them. Supports three draft types:
- **Pending new courses** (agent-created via `create_refined_course`)
- **Course drafts** (single-course changes via `create_course_draft`)
- **Document drafts** (multi-course changes via `create_document_draft`)

**Layout:** Two-column workspace. Left pane is a preview iframe showing either a single course or the full document. Right pane is the tabbed side panel. The toggle button expands/collapses the agent panel. The toolbar contains semester/course selectors, view mode switch, version controls, and status line.

**Attachments:** Users can upload files (PDF, DOC, DOCX, XLS, XLSX, CSV, TXT, MD, PNG, JPG, JPEG) for the agent to read. Text is extracted from documents; images are stored as base64. 10MB per file, 25MB total per session.

**View modes:** "Course Preview" shows one course. "Full Document" shows the entire curriculum PDF.

![Agentic Editor - Annotated](assets/images/editor_sample_annotated.png)
![Agentic Editor - Single Course](assets/images/editor_single_course.png)

## 6. Agent System

The agent is a tool-calling LLM loop (`openrouter.stream_chat`). It receives a system prompt (`chat.py:chat_system_prompt`) that instructs it to prefer granular read tools, create drafts for changes, and never apply them.

**System prompt structure:**
- Curriculum structure context (semester ranges, course code encoding, credit categories)
- Draft vs. direct creation guidelines
- Desirable knowledge guidance
- Agent acknowledgement instruction (brief text before tool calls)
- `update_agent_draft` tool mention for modifying existing drafts

**Tools** (`services/agent_tools.py`, registered in `TOOLS` -- 35 total):

*Read (course data)*
- `get_current_course_json` -- full template-ready course JSON
- `get_course_codes` -- lightweight IDs (refined_id, code, title, semester)
- `get_course_syllabus` -- units, objectives, course_outcomes
- `get_course_textbooks` -- text_books, reference_books
- `get_course_deterministic` -- protected fields (read-only context)
- `get_course_lab` -- lab experiments, tools/languages
- `get_course_fields` -- arbitrary field subset for one course
- `batch_read_courses` -- read specific fields from multiple courses in one call
- `get_curriculum_json` -- full curriculum, optionally by semester
- `list_courses` -- course IDs/titles, optionally by semester
- `get_curriculum_stats` -- aggregate statistics (total courses, credits per semester, course type distribution)

*Read (comparison/drafts)*
- `diff_course_json` -- compare two course JSONs
- `get_course_draft` / `get_document_draft` -- read staged drafts
- `get_version` -- load a curriculum version snapshot with its course list
- `diff_versions` -- compare two version snapshots (added/removed/changed courses)

*Read (specialization/external)*
- `get_course_assignments` -- which specialization tracks a course belongs to
- `list_specializations` -- list track definitions
- `get_attachment_text` -- read uploaded chat attachments
- `fetch_url` / `web_search` -- external context

*Write (always create reviewable drafts, never apply)*
- `create_course_draft` -- one course
- `update_agent_draft` -- merge fields into an existing draft (avoids duplicates)
- `create_document_draft` -- multiple courses
- `assign_elective_to_tracks` -- categorize an elective
- `remove_elective_from_tracks` -- remove a course from tracks
- `define_specialization` -- create a track
- `categorize_elective` -- AI-powered elective categorization into existing tracks
- `update_deterministic_fields` -- **the only** way to change protected fields; produces a `blocked` draft that requires explicit user approval

*Write (direct)*
- `create_refined_course` -- create new courses directly in refined_submissions (for brand-new courses only; for existing courses, use drafts)

*Generate (files/reports)*
- `create_spreadsheet` -- generate CSV or Excel (.xlsx) files from structured row data
- `create_report` -- generate markdown or PDF reports
- `create_curriculum_version` -- snapshot the current curriculum state
- `signal_done` -- signal task completion with a summary

**SSE event types** (streamed from `POST /chat/sessions/{id}/messages`):
- `status` -- status updates (model name, tool execution)
- `token` -- streamed text tokens from the LLM
- `tool_call` -- agent invoking a tool (name + arguments)
- `tool_result` -- tool execution result
- `draft` -- a course draft was created
- `document_draft` -- a document draft was created
- `refined_course` -- a new course was created directly
- `context_usage` -- token usage statistics
- `error` -- error occurred
- `done` -- stream complete

**Chat persistence:** All messages (user, assistant, tool_call, tool_result) are saved to `chat_messages` with role and metadata. Tool calls include the function name and arguments; tool results include the output. This enables conversation history across page refreshes.

**Agent output validation:**
- `desirable_knowledge` field: placeholder values (e.g., "None specified") are stripped by `_create_refined_course` to prevent invalid data.
- Draft-status courses: `_create_course_draft` rejects drafts for courses still in `draft` status, directing the agent to use `create_refined_course` instead.

## 7. Versioning

`GET/POST /api/versions` create named snapshots of the whole curriculum (`create_version_snapshot` copies every active `refined_submissions` into `finalized_submissions` pinned to a `curriculum_versions` row). `restore` overwrites current refined data from a snapshot, archives courses absent from the snapshot, and writes revision history.

The versions page lists snapshots, previews them (or a diff vs. current), and hands off to the editor. A "Current" entry at the top of the sidebar represents the live curriculum state. Version-vs-version comparison is supported via the compare controls.

![Version History - Default](assets/images/versions_default.png)
![Version History - Comparison](assets/images/versions_annotated_comparision.png)
![Version History - Rename](assets/images/versions_rename_category.png)
![Version History - Current](assets/images/versions_current_document.png)

---

## Caching

The system uses a dual cache layer (`services/cache.py`):

**Cache backends:**
- **Redis** (Upstash, optional): Set `REDIS_URL` to enable. Survives server restarts.
- **In-memory dict**: Fallback when Redis is unavailable. Survives within a process.

**Cache key prefixes and TTLs:**

| Prefix | TTL | Purpose |
| --- | --- | --- |
| `courses_list` | 180s | Course list for `/api/courses` |
| `course_pdf:` | 60s | Individual course PDF bytes |
| `version_list` | 180s | Version list for `/api/versions` |

**Invalidation:** Lazy (delete-on-write). When a mutation occurs (course update, version create, etc.), related cache keys are deleted. The next read misses the cache, fetches fresh data from Supabase, and re-caches.

**Prewarm:** On startup, the cache is prewarmed with course and version lists.

**Debug mode:** Set `is_cache_disabled = True` in `cache.py` to bypass caching entirely (useful for development).

---

## Error Handling & Retry

The OpenRouter client (`services/openrouter.py`) implements a retry and fallback system for LLM calls:

**Retry behavior:**
- **Retryable statuses:** 502, 503 (server errors)
- **Retryable exceptions:** `httpx.TimeoutException`, `httpx.TransportError`
- **NOT retried:** 429 (rate limit) -- shows error and stops immediately
- **Backoff:** Fibonacci sequence `[1, 1, 2, 3, 5, 8, 13]` seconds with +/-25% jitter
- **Max retries:** 3 per request
- **Retry-After header:** Respected when present

**Fallback model:**
- Set `OPENROUTER_FALLBACK_MODEL` env var to enable (e.g. `google/gemma-3-27b-it:free`)
- After 3 failed retries on the primary model, the system commits to the fallback model for the rest of the chat thread
- The fallback is announced via SSE `status` events so the UI can inform the user
- Once committed, `active_model` persists as the fallback for all subsequent calls

**429 (rate limit) handling:**
- No retry, no fallback
- Error message shown in chat and status bar
- User must wait and retry manually

**Chat streaming errors:**
- Errors are surfaced as SSE `error` events
- The UI creates an error bubble in the chat even when no tokens were received
- The `done` handler reloads messages from the database to ensure persistence