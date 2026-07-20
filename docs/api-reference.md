---
title: API Reference
layout: default
permalink: /api-reference/
---

# API Reference

All paths are prefixed with `/api` at runtime.

## Health

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health/schema` | GET | Verify required Supabase tables exist. Returns 503 if tables are missing. |

## Submissions

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/submissions` | POST | Store a raw submission, queue background refinement. Body: `CourseSubmission`. |
| `/api/submissions/{id}/refine` | POST | Manually trigger refinement for an existing submission. |

## Refined Courses

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/refined/{refined_id}` | GET | Read template-ready course fields. |
| `/api/refined/{refined_id}` | PATCH | Update editable refined fields. Promotes draft-status courses to refined. Body: `{ fields: dict }`. |

## Course Management

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/courses` | GET | List active refined courses (cached 180s). |
| `/api/courses/{refined_id}/visible` | PATCH | Toggle course visibility. Body: `{ visible: bool }`. |
| `/api/courses/{refined_id}` | DELETE | Soft-delete (archive) a course. |

## Preview & PDF

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/preview/course/{refined_id}` | GET | Render one course as HTML. |
| `/api/preview/course/{refined_id}/pdf` | GET | Generate PDF for one course. `?download=true` for attachment. |
| `/api/preview/html` | GET | Render full curriculum as HTML. |
| `/api/preview/pdf` | GET | Generate full curriculum PDF. `?download=true` for attachment. |
| `/api/preview/semester/{sem}/pdf` | GET | Generate one semester as PDF. |
| `/api/preview/semester/{sem}/courses` | GET | List course IDs for a semester. |
| `/api/preview/pending-courses` | GET | List draft-status (pending) courses. |
| `/api/preview/courses` | GET | List all visible refined course IDs. |

## Agent Drafts

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/agent/drafts` | GET | List 100 most recent agent drafts. |
| `/api/agent/drafts` | POST | Create a single-course draft. Body: `{ refined_id, fields, reason? }`. |
| `/api/agent/drafts/{draft_id}` | GET | Fetch a draft with base/proposed JSON and diff summary. |
| `/api/agent/drafts/{draft_id}/apply` | POST | Apply a proposed draft. Rejects blocked drafts or protected-field changes. |
| `/api/agent/drafts/{draft_id}/preview` | GET | Render draft as HTML. `?diff=true` for diff view. |

## Document Drafts (multi-course)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/agent/document-drafts` | GET | List 100 most recent document drafts. |
| `/api/agent/document-drafts` | POST | Create a multi-course draft. Body: `{ courses: [{ refined_id, fields }], reason? }`. |
| `/api/agent/document-drafts/{id}` | GET | Fetch document draft with all linked course drafts. |
| `/api/agent/document-drafts/{id}/apply` | POST | Apply all proposed sub-drafts. |
| `/api/agent/document-drafts/{id}/preview` | GET | Render all proposed courses. `?diff=true` for diff view. |

## Agent Tools & Diff

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/agent/tools` | GET | List all agent tool schemas (OpenAI function-calling format). |
| `/api/agent/tools/{tool_name}` | POST | Execute a tool directly. Body: `{ arguments: dict }`. |
| `/api/agent/context-length` | GET | Return current model's context window size. |
| `/api/agent/diff` | POST | Compute structured diff between two course JSONs. |

## Chat

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat/sessions` | GET | List active sessions. `?refined_id=` or `?document_draft_id=` to filter. |
| `/api/chat/sessions` | POST | Create a session. Body: `{ refined_id?, document_draft_id?, title? }`. |
| `/api/chat/sessions/{id}` | PATCH | Rename a session. Body: `{ title }`. |
| `/api/chat/sessions/{id}` | DELETE | Soft-archive a session and its messages. |
| `/api/chat/sessions/{id}/messages` | GET | Fetch all messages in a session. |
| `/api/chat/sessions/{id}/messages` | POST | Send a message and stream response via SSE. Events: `status`, `token`, `tool_call`, `tool_result`, `draft`, `document_draft`, `refined_course`, `context_usage`, `error`, `done`. |
| `/api/chat/sessions/{id}/attachments` | POST | Upload files (multipart/form-data). 10MB/file, 25MB total. |
| `/api/chat/sessions/{id}/attachments/{att_id}/download` | GET | Download an attachment. |
| `/api/chat/sessions/{id}/attachments/{att_id}/preview` | GET | Preview an attachment inline. |

## Versions

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/versions` | GET | List all curriculum snapshots. Includes `course_count` and `has_changes`. |
| `/api/versions` | POST | Create a snapshot. Returns 409 if no changes since last version. Body: `{ name, program?, academic_year?, status? }`. |
| `/api/versions/{version_id}` | GET | Fetch version with its course list. |
| `/api/versions/{version_id}` | PATCH | Update version metadata. Body: `{ name?, academic_year?, status? }`. |
| `/api/versions/{version_id}` | DELETE | Delete a version and its finalized_submissions. |
| `/api/versions/{version_id}/restore` | POST | Restore a snapshot. Archives absent courses. Resets applied drafts. |
| `/api/versions/{version_id}/courses/{refined_id}` | GET | Fetch a single course snapshot from a version. |
| `/api/versions/{version_id}/courses/{refined_id}/preview` | GET | Render a version course as HTML. |
| `/api/versions/{version_id}/preview` | GET | Render all version courses. `?diff=true` for diff vs current. |
| `/api/versions/{id1}/diff/{id2}` | GET | Render side-by-side diff between two versions. |

## Query Parameters

| Parameter | Applies to | Description |
|-----------|------------|-------------|
| `curriculum_year` | All preview/PDF endpoints | Pin the batch year (e.g. `2025-2026`). Falls back to `CURRICULUM_YEAR` env var. |
| `download` | PDF endpoints | Set `true` to trigger Content-Disposition attachment. |
| `diff` | Draft/version preview | Set `true` to render diff view instead of proposed content. |

**Total: 49 endpoints** across 9 route files.