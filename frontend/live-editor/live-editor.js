if (typeof marked !== "undefined") {
  marked.use({ gfm: true, breaks: false });
}

function preprocessUrls(text) {
  return text.replace(
    /(?<!\()(https?:\/\/[^\s<>"')\]]+)/g,
    (url) => {
      const clean = url.replace(/[.,;:!?]+$/, "");
      const trailing = url.slice(clean.length);
      return `[${clean}](${clean})${trailing}`;
    }
  );
}

function yearParam(base) {
  const y = localStorage.getItem("curriculumYear") || "";
  if (!y) return base;
  const sep = base.includes("?") ? "&" : "?";
  return `${base}${sep}curriculum_year=${encodeURIComponent(y)}`;
}

const semester = document.getElementById("semester");
const course = document.getElementById("course");
const viewMode = document.getElementById("view-mode");
const versionName = document.getElementById("version-name");
const saveVersion = document.getElementById("save-version");
const versionSelect = document.getElementById("version-select");
const restoreVersion = document.getElementById("restore-version");
const preview = document.getElementById("preview");
const viewer = document.getElementById("viewer");
const loading = document.getElementById("loading");
const statusText = document.getElementById("status");
const chatTab = document.getElementById("chat-tab");
const fieldsTab = document.getElementById("fields-tab");
const reviewTab = document.getElementById("review-tab");
const chatPanel = document.getElementById("chat-panel");
const fieldsPanel = document.getElementById("fields-panel");
const reviewPanel = document.getElementById("review-panel");
const chatSession = document.getElementById("chat-session");
const chatTitle = document.getElementById("chat-title");
const renameChat = document.getElementById("rename-chat");
const deleteChat = document.getElementById("delete-chat");
const newChat = document.getElementById("new-chat");
const chatLog = document.getElementById("chat-log");
const chatStatus = document.getElementById("chat-status");
const chatStatusText = document.getElementById("chat-status-text");
const chatSpinner = document.getElementById("chat-spinner");
const message = document.getElementById("message");
const attach = document.getElementById("attach");
const files = document.getElementById("files");
const draftAttachments = document.getElementById("draft-attachments");
const send = document.getElementById("send");
const stopBtn = document.getElementById("stop-btn");
const versionDisplay = document.getElementById("version-display");

const editor = document.getElementById("editor");
const draft = document.getElementById("draft");
const save = document.getElementById("save");
const pendingCourseSelect = document.getElementById("pending-course-select");
const loadPendingCourse = document.getElementById("load-pending-course");
const courseDraftSelect = document.getElementById("course-draft-select");
const loadCourseDraft = document.getElementById("load-course-draft");
const documentDraftSelect = document.getElementById("document-draft-select");
const loadDocumentDraft = document.getElementById("load-document-draft");
const reviewSummary = document.getElementById("review-summary");
const diffView = document.getElementById("diff-view");
const previewDraft = document.getElementById("preview-draft");
const applyDraft = document.getElementById("apply-draft");
const togglePane = document.getElementById("toggle-pane");
const logoutBtn = document.getElementById("logout-btn");
const previewOverlay = document.getElementById("preview-overlay");
const previewFilename = document.getElementById("preview-filename");
const previewBody = document.getElementById("preview-body");
const previewClose = document.getElementById("preview-close");
const contextBadge = document.getElementById("context-badge");
const contextUsage = document.getElementById("context-usage");

fetch("/api/agent/context-length").then((r) => r.json()).then((d) => {
  const tokens = d.context_length || 0;
  contextBadge.textContent = tokens >= 1000000 ? `${tokens / 1000000}M` : tokens >= 1000 ? `${Math.round(tokens / 1000)}K` : `${tokens}`;
  contextBadge.title = `${d.model} - ${tokens.toLocaleString()} tokens`;
}).catch(() => {});

const TOOL_LABELS = {
  get_course_codes: "Looking up courses",
  get_current_course_json: "Reading course data",
  get_course_syllabus: "Reading syllabus",
  get_course_textbooks: "Reading textbooks",
  get_course_deterministic: "Reading course properties",
  get_course_lab: "Reading lab details",
  get_course_fields: "Reading course fields",
  batch_read_courses: "Reading courses",
  get_curriculum_json: "Loading curriculum",
  get_curriculum_stats: "Computing statistics",
  create_course_draft: "Creating draft",
  create_refined_course: "Creating course",
  create_document_draft: "Creating document draft",
  create_report: "Generating report",
  create_spreadsheet: "Generating spreadsheet",
  diff_course_json: "Comparing courses",
  diff_versions: "Comparing versions",
  get_version: "Loading snapshot",
  update_deterministic_fields: "Updating course",
  get_attachment_text: "Reading attachment",
  list_specializations: "Loading specializations",
  define_specialization: "Creating specialization",
  assign_elective_to_tracks: "Categorizing elective",
  get_course_assignments: "Reading elective assignments",
  fetch_url: "Fetching URL",
  web_search: "Searching the web",
  signal_done: "Finalizing",
  get_document_draft: "Reading document draft",
  create_curriculum_version: "Creating snapshot",
  get_course_draft: "Reading draft",
  remove_elective_from_tracks: "Removing elective",
  get_preview_url: "Getting preview URL",
  list_courses: "Looking up courses",
};

let activeCourseId = "";
let activeDraftId = "";
let activeDraftRefinedId = "";
let activeDocumentDraftId = "";
let activeSessionId = "";
let chatLoadSeq = 0;
let queuedFiles = [];
let versionMode = false;
let activeAbortController = null;
let currentVersionName = "";
const initialParams = new URLSearchParams(location.search);

if (logoutBtn) {
  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem("sb-supgrlinqgxvifijgbns-auth-token");
    location.href = "/auth/";
  });
}

if (stopBtn) {
  stopBtn.addEventListener("click", () => {
    if (activeAbortController) {
      activeAbortController.abort();
      activeAbortController = null;
    }
  });
}

function hideCourseControls() {
  semester.hidden = true;
  course.hidden = true;
  const previewBtn = document.getElementById("preview");
  if (previewBtn) previewBtn.hidden = false;
}

function showCourseControls() {
  semester.hidden = false;
  course.hidden = false;
  const previewBtn = document.getElementById("preview");
  if (previewBtn) previewBtn.hidden = true;
}

function updateRestoreVisibility() {
  if (!restoreVersion) return;
  const firstOption = versionSelect.options[0];
  const isLatest = !firstOption || firstOption.value === versionSelect.value;
  restoreVersion.hidden = isLatest || versionMode;
}

function updateVersionDisplay(name) {
  currentVersionName = name || "";
  if (versionDisplay) {
    if (name) {
      versionDisplay.textContent = name;
      versionDisplay.hidden = false;
    } else {
      versionDisplay.hidden = true;
    }
  }
}

function setStatus(text, kind = "") {
  statusText.textContent = text || "";
  statusText.className = kind;
  statusText.hidden = !text;
}

function showError(error, fallback = "Action failed.") {
  loading.classList.remove("active");
  const text = error instanceof Error ? error.message : fallback;
  setStatus(text || fallback, "error");
}

async function errorMessage(response, fallback) {
  try {
    const body = await response.json();
    return body.detail || body.message || fallback;
  } catch {
    return fallback;
  }
}

async function courseIds(sem) {
  const response = await fetch(`/api/preview/semester/${sem}/courses`);
  if (!response.ok) return [];
  const body = await response.json();
  return body.course_ids || [];
}

async function courseEntries(sem) {
  const response = await fetch(`/api/preview/semester/${sem}/courses`);
  if (!response.ok) return [];
  const body = await response.json();
  return body.courses || [];
}

async function firstAvailableSemester() {
  for (let sem = 1; sem <= 8; sem += 1) {
    if ((await courseIds(sem)).length) return String(sem);
  }
  return "1";
}

function setTab(name) {
  const chat = name === "chat";
  const fields = name === "fields";
  const review = name === "review";
  chatTab.classList.toggle("active", chat);
  fieldsTab.classList.toggle("active", fields);
  reviewTab.classList.toggle("active", review);
  chatTab.setAttribute("aria-selected", String(chat));
  fieldsTab.setAttribute("aria-selected", String(fields));
  reviewTab.setAttribute("aria-selected", String(review));
  chatPanel.classList.toggle("active", chat);
  fieldsPanel.classList.toggle("active", fields);
  reviewPanel.classList.toggle("active", review);
  if (review) refreshDraftSelectors().catch(() => {});
}

function chatKey() {
  return `pesu-live-editor-session:${activeCourseId || "document"}`;
}

function option(value, text) {
  const item = document.createElement("option");
  item.value = value;
  item.textContent = text;
  return item;
}

function versionLabel(item) {
  const year = item.academic_year ? ` ${item.academic_year}` : "";
  return `${item.name}${year}`;
}

async function refreshVersions() {
  const response = await fetch("/api/versions");
  if (!response.ok) return;
  const body = await response.json();
  versionSelect.replaceChildren(...(body.versions || []).map((item) => option(String(item.id), versionLabel(item))));
  updateRestoreVisibility();
}

async function saveCurrentVersion() {
  const name = versionName.value.trim();
  if (!name) {
    setStatus("Version name is required.", "error");
    return;
  }
  saveVersion.disabled = true;
  try {
    setStatus("Saving full version...");
    const response = await fetch("/api/versions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!response.ok) throw new Error(await errorMessage(response, "Version save failed"));
    const body = await response.json();
    versionName.value = "";
    await refreshVersions();
    versionSelect.value = String(body.version.id);
    setStatus(`Saved ${body.courses} courses.`, "ready");
  } finally {
    saveVersion.disabled = false;
  }
}

async function restoreSelectedVersion() {
  if (!versionSelect.value) return;
  if (!await showConfirm("Restore this version? This will archive all current courses and replace them with the snapshot.")) return;
  restoreVersion.disabled = true;
  try {
    setStatus("Restoring full version...");
    const response = await fetch(`/api/versions/${versionSelect.value}/restore`, { method: "POST" });
    if (!response.ok) throw new Error(await errorMessage(response, "Version restore failed"));
    const body = await response.json();
    if (activeCourseId) await loadCourse(activeCourseId);
    setStatus(`Restored ${body.courses_restored} courses. Archived ${body.courses_archived || 0}.`, "ready");
  } finally {
    restoreVersion.disabled = false;
  }
}

function chatScopeQuery() {
  return activeCourseId ? `?refined_id=${encodeURIComponent(activeCourseId)}` : "";
}

function sessionTitle(item) {
  if (item.title) return item.title;
  const date = item.created_at ? new Date(item.created_at).toLocaleDateString() : "";
  return date ? `Thread ${item.id} - ${date}` : `Thread ${item.id}`;
}

async function refreshChatSessions() {
  const response = await fetch(`/api/chat/sessions${chatScopeQuery()}`);
  if (!response.ok) return;
  const body = await response.json();
  const sessions = body.sessions || [];
  chatSession.replaceChildren(...sessions.map((item) => option(String(item.id), sessionTitle(item))));
  if (activeSessionId) chatSession.value = activeSessionId;
  const selected = sessions.find((item) => String(item.id) === chatSession.value);
  if (chatTitle.hidden) chatTitle.value = selected?.title || "";
}

async function createChatSession() {
  const response = await fetch("/api/chat/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(activeCourseId ? { refined_id: Number(activeCourseId), title: statusText.textContent } : { title: "New Thread" }),
  });
  if (!response.ok) throw new Error("Unable to create agent session");
  const body = await response.json();
  activeSessionId = String(body.session.id);
  localStorage.setItem(chatKey(), activeSessionId);
  await refreshChatSessions();
  chatSession.value = activeSessionId;
  return activeSessionId;
}

async function renameActiveChat() {
  if (!activeSessionId || !chatTitle.value.trim()) {
    exitRenameMode();
    return;
  }
  const response = await fetch(`/api/chat/sessions/${activeSessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: chatTitle.value.trim() }),
  });
  if (!response.ok) throw new Error(await errorMessage(response, "Rename failed"));
  await refreshChatSessions();
  setStatus("Thread renamed.", "ready");
  exitRenameMode();
}

function enterRenameMode() {
  if (!activeSessionId) return;
  const currentTitle = chatSession.options[chatSession.selectedIndex]?.text || "";
  chatTitle.value = currentTitle;
  chatTitle.hidden = false;
  document.querySelector(".thread-selector").hidden = true;
  chatTitle.focus();
  chatTitle.select();
}

function exitRenameMode() {
  chatTitle.hidden = true;
  const selector = document.querySelector(".thread-selector");
  if (selector) selector.hidden = false;
}

async function deleteActiveChat() {
  if (!activeSessionId) return;
  if (!await showConfirm("Delete this agent thread permanently?")) return;
  const deleted = activeSessionId;
  const response = await fetch(`/api/chat/sessions/${deleted}`, { method: "DELETE" });
  if (!response.ok) throw new Error(await errorMessage(response, "Delete failed"));
  localStorage.removeItem(chatKey());
  activeSessionId = "";
  chatLog.replaceChildren();
  await ensureChatSession();
  await renderMessages();
  setStatus("Thread deleted.", "ready");
}

async function ensureChatSession() {
  const key = chatKey();
  const existing = localStorage.getItem(key);
  if (existing) {
    activeSessionId = existing;
    await refreshChatSessions();
    if ([...chatSession.options].some((item) => item.value === existing)) return existing;
    localStorage.removeItem(key);
    activeSessionId = "";
  }
  await refreshChatSessions();
  if (chatSession.value) {
    activeSessionId = chatSession.value;
    localStorage.setItem(key, activeSessionId);
    return activeSessionId;
  }
  return createChatSession();
}

async function loadMessages() {
  if (!activeSessionId) return [];
  const response = await fetch(`/api/chat/sessions/${activeSessionId}/messages`);
  if (!response.ok) {
    localStorage.removeItem(chatKey());
    activeSessionId = "";
    await ensureChatSession();
    return [];
  }
  const body = await response.json();
  return body.messages || [];
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function attachmentNode(file, index, removable) {
  const item = document.createElement("div");
  item.className = "attachment";
  const visual = file.preview ? document.createElement("img") : document.createElement("div");
  if (file.preview) {
    visual.src = file.preview;
    visual.alt = "";
  } else {
    visual.className = "attachment-icon";
    const mime = (file.type || "").toLowerCase();
    let icon = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;
    let label = "FILE";
    if (mime.includes("pdf")) {
      icon = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M9 15h2"/><path d="M9 11h6"/><path d="M9 19h6"/></svg>`;
      label = "PDF";
    } else if (mime.includes("spreadsheet") || mime.includes("excel") || mime.endsWith(".xlsx") || mime.endsWith(".csv")) {
      icon = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/><line x1="15" y1="3" x2="15" y2="21"/></svg>`;
      label = "XLS";
    } else if (mime.includes("word") || mime.includes("document") || mime.endsWith(".doc") || mime.endsWith(".docx")) {
      icon = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="13" y2="17"/></svg>`;
      label = "DOC";
    } else if (mime.includes("markdown") || (file.name || "").endsWith(".md")) {
      icon = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M7 15V9l2.5 3L12 9v6"/><path d="M14 15l2-3 2 3"/></svg>`;
      label = "MD";
    } else if (mime.includes("text") || mime.endsWith(".txt")) {
      icon = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/><line x1="8" y1="9" x2="10" y2="9"/></svg>`;
      label = "TXT";
    } else if (mime.includes("image")) {
      icon = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`;
      label = "IMG";
    }
    visual.innerHTML = `<span class="attachment-icon-label">${label}</span>${icon}`;
  }
  const text = document.createElement("div");
  const name = document.createElement("div");
  name.className = "attachment-name";
  name.textContent = file.name;
  const meta = document.createElement("div");
  meta.className = "attachment-meta";
  if (file.status) meta.classList.add(file.status);
  const status = file.status ? ` - ${file.status}` : "";
  const extracted = file.extracted_chars ? ` - ${file.extracted_chars} chars` : "";
  meta.textContent = `${file.type || "file"} - ${formatSize(file.size || 0)}${status}${extracted}`;
  text.append(name, meta);
  item.append(visual, text);
  const actions = document.createElement("div");
  actions.className = "attachment-actions";
  if (removable) {
    const remove = document.createElement("button");
    remove.className = "attachment-remove";
    remove.type = "button";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => {
      queuedFiles.splice(index, 1);
      renderDraftAttachments();
    });
    actions.appendChild(remove);
  } else if (file.id) {
    const preview = document.createElement("button");
    preview.className = "attachment-preview";
    preview.type = "button";
    preview.textContent = "Preview";
    preview.addEventListener("click", () => openPreview(file));
    actions.appendChild(preview);
    const dl = document.createElement("a");
    dl.className = "attachment-download";
    dl.href = `/api/chat/sessions/${activeSessionId}/attachments/${file.id}/download`;
    dl.download = file.name || "download";
    dl.title = "Download";
    dl.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';
    actions.appendChild(dl);
  }
  item.appendChild(actions);
  return item;
}

function renderDraftAttachments() {
  draftAttachments.replaceChildren(...queuedFiles.map((file, index) => attachmentNode(file, index, true)));
}

async function openPreview(file) {
  if (!file.id || !activeSessionId) return;
  previewFilename.textContent = file.name || "Preview";
  previewBody.innerHTML = '<div class="preview-loading">Loading preview...</div>';
  previewOverlay.hidden = false;
  const mime = (file.type || "").toLowerCase();
  const name = (file.name || "").toLowerCase();
  try {
    const url = `/api/chat/sessions/${activeSessionId}/attachments/${file.id}/preview`;
    const response = await fetch(url);
    if (!response.ok) throw new Error("Preview failed");
    if (mime === "application/pdf" || name.endsWith(".pdf")) {
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      previewBody.innerHTML = `<iframe src="${blobUrl}" class="preview-iframe"></iframe>`;
    } else if (mime.includes("markdown") || name.endsWith(".md")) {
      const text = await response.text();
      const html = typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(marked.parse(preprocessUrls(text))) : marked.parse(preprocessUrls(text));
      previewBody.innerHTML = `<div class="preview-rendered">${html}</div>`;
    } else if (mime.includes("spreadsheet") || mime.includes("excel") || name.endsWith(".xlsx") || name.endsWith(".csv")) {
      const text = await response.text();
      const table = csvToTable(text, name.endsWith(".csv"));
      previewBody.innerHTML = table;
    } else if (mime.includes("word") || name.endsWith(".doc") || name.endsWith(".docx")) {
      const text = await response.text();
      previewBody.innerHTML = `<pre class="preview-text">${escapeHtml(text)}</pre>`;
    } else {
      const text = await response.text();
      previewBody.innerHTML = `<pre class="preview-text">${escapeHtml(text)}</pre>`;
    }
  } catch (error) {
    previewBody.innerHTML = `<div class="preview-error">Could not load preview.</div>`;
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function csvToTable(text, isCsv) {
  const lines = text.split("\n").filter((l) => l.trim());
  if (!lines.length) return `<pre class="preview-text">${escapeHtml(text)}</pre>`;
  const rows = lines.map((line) => {
    const cells = [];
    let current = "";
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (inQuotes) {
        if (ch === '"' && line[i + 1] === '"') { current += '"'; i++; }
        else if (ch === '"') inQuotes = false;
        else current += ch;
      } else {
        if (ch === '"') inQuotes = true;
        else if (ch === "\t" || (isCsv && ch === ",")) { cells.push(current); current = ""; }
        else current += ch;
      }
    }
    cells.push(current);
    return cells;
  });
  const header = rows.shift();
  if (!header) return `<pre class="preview-text">${escapeHtml(text)}</pre>`;
  let html = '<table class="preview-table"><thead><tr>';
  header.forEach((h) => { html += `<th>${escapeHtml(h)}</th>`; });
  html += "</tr></thead><tbody>";
  rows.forEach((row) => {
    html += "<tr>";
    row.forEach((cell) => { html += `<td>${escapeHtml(cell)}</td>`; });
    html += "</tr>";
  });
  html += "</tbody></table>";
  return html;
}

function closePreview() {
  const iframe = previewBody.querySelector("iframe");
  if (iframe && iframe.src.startsWith("blob:")) URL.revokeObjectURL(iframe.src);
  previewOverlay.hidden = true;
  previewBody.innerHTML = "";
}

previewClose.addEventListener("click", closePreview);
previewOverlay.addEventListener("click", (e) => { if (e.target === previewOverlay) closePreview(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !previewOverlay.hidden) closePreview(); });

function messageNode(item) {
  const bubble = document.createElement("div");
  bubble.className = `message ${item.role}`;
  if (item.role === "tool") {
    const callType = item.metadata?.tool_call_type || (item.content || "").startsWith("\u2699") ? "call" : "result";
    bubble.classList.add(callType === "call" ? "tool-call" : "tool-result");
  }
  const content = document.createElement("div");
  content.className = "message-body";
  renderMessageContent(content, item.content || "");
  bubble.appendChild(content);
  const attachments = item.attachments || item.metadata?.attachments || [];
  if (attachments.length) {
    const list = document.createElement("div");
    list.className = "attachments";
    attachments.forEach((file) => list.appendChild(attachmentNode(file, 0, false)));
    bubble.appendChild(list);
  }
  const time = document.createElement("div");
  time.className = "message-time";
  time.textContent = new Date(item.created_at || Date.now()).toLocaleString();
  bubble.appendChild(time);
  return { bubble, content };
}

function renderInline(parent, text) {
  if (typeof marked !== "undefined") {
    parent.innerHTML = typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(marked.parse(preprocessUrls(text))) : marked.parse(preprocessUrls(text));
    return;
  }
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|https?:\/\/[^\s<>"']+)/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) parent.appendChild(document.createTextNode(text.slice(last, match.index)));
    const token = match[0];
    if (token.startsWith("**")) {
      const strong = document.createElement("strong");
      strong.textContent = token.slice(2, -2);
      parent.appendChild(strong);
    } else if (token.startsWith("`")) {
      const code = document.createElement("code");
      code.textContent = token.slice(1, -1);
      parent.appendChild(code);
    } else {
      const link = document.createElement("a");
      const url = token.replace(/[.,;:)}!?]+$/, "").replace(/[<>]+/g, "");
      const trailing = token.slice(url.length);
      link.href = url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = url;
      parent.appendChild(link);
      if (trailing) parent.appendChild(document.createTextNode(trailing));
    }
    last = match.index + token.length;
  }
  if (last < text.length) parent.appendChild(document.createTextNode(text.slice(last)));
}

function renderMessageContent(target, value) {
  target.replaceChildren();
  const text = String(value || "");
  if (typeof marked !== "undefined") {
    target.innerHTML = typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(marked.parse(preprocessUrls(text))) : marked.parse(preprocessUrls(text));
    return;
  }
  const lines = text.split("\n");
  let inList = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    if (!trimmed) {
      inList = false;
      continue;
    }
    if (/^---+$/.test(trimmed)) {
      if (inList) inList = false;
      target.appendChild(document.createElement("hr"));
      continue;
    }
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      if (!inList) {
        inList = true;
        target.appendChild(document.createElement("ul"));
      }
      const li = document.createElement("li");
      renderInline(li, trimmed.slice(2));
      target.lastElementChild.appendChild(li);
      continue;
    }
    if (inList) inList = false;
    const block = document.createElement("div");
    renderInline(block, line);
    target.appendChild(block);
  }
}

function appendMessage(item) {
  const node = messageNode(item);
  chatLog.appendChild(node.bubble);
  chatLog.scrollTop = chatLog.scrollHeight;
  return node;
}

async function renderMessages() {
  const seq = ++chatLoadSeq;
  const messages = await loadMessages();
  if (seq !== chatLoadSeq) return;
  chatLog.replaceChildren();
  messages.forEach((item) => appendMessage(item));
  chatStatusText.textContent = "";
  chatSpinner.classList.remove("active");
}

function parseEvent(raw) {
  let event = "message";
  const data = [];
  raw.split("\n").forEach((line) => {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data.push(line.slice(5).trim());
  });
  return { event, data: data.length ? JSON.parse(data.join("\n")) : {} };
}

async function readEventStream(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index = buffer.indexOf("\n\n");
    while (index >= 0) {
      const raw = buffer.slice(0, index).trim();
      buffer = buffer.slice(index + 2);
      if (raw) {
        try {
          onEvent(parseEvent(raw));
        } catch (e) {
          console.warn("SSE parse error:", e);
        }
      }
      index = buffer.indexOf("\n\n");
    }
  }
}

function resetReview() {
  activeDraftId = "";
  activeDraftRefinedId = "";
  activeDocumentDraftId = "";
  reviewSummary.replaceChildren(document.createTextNode("No draft loaded."));
  renderDiff("");
  previewDraft.disabled = true;
  applyDraft.disabled = true;
}

function renderDiff(text) {
  diffView.replaceChildren();
  if (!text) {
    const empty = document.createElement("div");
    empty.className = "diff-empty";
    empty.textContent = "No diff loaded.";
    diffView.appendChild(empty);
    return;
  }

  text.split("\n").forEach((line) => {
    let kind = "context";
    let sign = "";
    let code = line;

    if (line.startsWith("Course draft ")) {
      kind = "title";
    } else if (line.startsWith("@@")) {
      kind = "header";
    } else if (line.startsWith("---") || line.startsWith("+++")) {
      kind = "meta";
    } else if (line.startsWith("-")) {
      kind = "removed";
      sign = "-";
      code = line.slice(1).replace(/^ /, "");
    } else if (line.startsWith("+")) {
      kind = "added";
      sign = "+";
      code = line.slice(1).replace(/^ /, "");
    }

    const row = document.createElement("div");
    row.className = `diff-row ${kind}`;
    const signCell = document.createElement("div");
    signCell.className = "diff-sign";
    signCell.textContent = sign;
    const codeCell = document.createElement("div");
    codeCell.className = "diff-code";
    codeCell.textContent = code;
    row.append(signCell, codeCell);
    diffView.appendChild(row);
  });
}

function summaryLine(label, value) {
  const line = document.createElement("div");
  const strong = document.createElement("strong");
  strong.textContent = `${label}: `;
  line.append(strong, document.createTextNode(value));
  return line;
}

function renderDraftReview(draftRow) {
  const summary = draftRow.diff_summary || {};
  activeDraftId = String(draftRow.id || "");
  activeDraftRefinedId = String(draftRow.refined_id || "");
  reviewSummary.replaceChildren(
    summaryLine("Draft", activeDraftId || "unsaved"),
    summaryLine("Status", draftRow.status || ""),
    summaryLine("Change", `${summary.change_percent || 0}%`),
    summaryLine("Syllabus change", `${summary.syllabus_change_percent || 0}%`),
    summaryLine("Topics added", (summary.topics_added || []).join(", ") || "None"),
    summaryLine("Topics removed", (summary.topics_removed || []).join(", ") || "None"),
    summaryLine("Protected changes", (summary.protected_changes || []).join(", ") || "None"),
  );
  renderDiff(summary.unified_diff || "No changes.");
  previewDraft.disabled = !activeDraftId;
  applyDraft.disabled = draftRow.status !== "proposed" || Boolean((summary.protected_changes || []).length);
}

function showCourseDraft(draftRow) {
  renderDraftReview(draftRow);
  viewer.src = yearParam(`/api/agent/drafts/${draftRow.id}/preview?diff=1`);
  setStatus("Draft ready for review.", "ready");
  refreshDraftSelectors().catch(showError);
  setTab("review");
}

async function loadCourseDraftById(id) {
  if (!id) return;
  setStatus("Loading course draft...");
  const response = await fetch(`/api/agent/drafts/${id}`);
  if (!response.ok) throw new Error(await errorMessage(response, "Course draft not found"));
  const body = await response.json();
  showCourseDraft(body.draft);
  setStatus("Course draft loaded.", "ready");
}

async function loadDocumentDraftById(id) {
  if (!id) return;
  setStatus("Loading document draft...");
  const response = await fetch(`/api/agent/document-drafts/${id}`);
  if (!response.ok) throw new Error(await errorMessage(response, "Document draft not found"));
  const body = await response.json();
  const summary = body.document_draft.diff_summary || {};
  activeDraftId = "";
  activeDocumentDraftId = String(id);
  reviewSummary.replaceChildren(
    summaryLine("Document draft", id),
    summaryLine("Status", body.document_draft.status || ""),
    summaryLine("Courses changed", String(summary.courses_changed || 0)),
    summaryLine("Removed-topic courses", String(summary.courses_with_removed_topics || 0)),
    summaryLine("Protected-change courses", String(summary.courses_with_protected_changes || 0)),
    summaryLine("Max syllabus change", `${summary.max_syllabus_change_percent || 0}%`),
  );
  renderDiff(
    (body.drafts || [])
      .map((item) => `Course draft ${item.id}\n${item.diff_summary?.unified_diff || ""}`)
      .join("\n\n"),
  );
  previewDraft.disabled = false;
  applyDraft.disabled = body.document_draft.status !== "proposed" || Boolean(summary.courses_with_protected_changes);
  viewer.src = yearParam(`/api/agent/document-drafts/${id}/preview?diff=1`);
  await refreshDraftSelectors();
  documentDraftSelect.value = String(id);
  setTab("review");
  setStatus("Document draft loaded.", "ready");
}

function courseDraftLabel(item) {
  const title = item.course_title || `Course ${item.refined_id}`;
  const code = item.course_code ? `${item.course_code} - ` : "";
  return `${item.id}: ${code}${title} (${item.status})`;
}

function documentDraftLabel(item) {
  const name = item.uploaded_document_id || item.change_reason || `Document draft ${item.id}`;
  return `${item.id}: ${name} (${item.status})`;
}

async function refreshDraftSelectors() {
  const [courseResponse, documentResponse] = await Promise.all([
    fetch("/api/agent/drafts"),
    fetch("/api/agent/document-drafts"),
  ]);
  if (courseResponse.ok) {
    const body = await courseResponse.json();
    courseDraftSelect.replaceChildren(...(body.drafts || []).filter((item) => item.status !== "applied").map((item) => option(String(item.id), courseDraftLabel(item))));
  }
  if (documentResponse.ok) {
    const body = await documentResponse.json();
    documentDraftSelect.replaceChildren(...(body.document_drafts || []).filter((item) => item.status !== "applied").map((item) => option(String(item.id), documentDraftLabel(item))));
  }
  if (activeDraftId) courseDraftSelect.value = activeDraftId;
  await refreshPendingCourses();
}

function filePreview(file) {
  return new Promise((resolve) => {
    if (!file.type.startsWith("image/") || file.size > 900000) {
      resolve("");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => resolve("");
    reader.readAsDataURL(file);
  });
}

async function queueFiles(fileList) {
  await ensureChatSession();
  setStatus("Uploading attachments...");
  const pending = await Promise.all(
    Array.from(fileList).map(async (file) => ({
      name: file.name,
      type: file.type,
      size: file.size,
      status: "uploading",
      preview: await filePreview(file),
    })),
  );
  queuedFiles = queuedFiles.concat(pending);
  renderDraftAttachments();
  const form = new FormData();
  Array.from(fileList).forEach((file) => form.append("files", file));
  const response = await fetch(`/api/chat/sessions/${activeSessionId}/attachments`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Attachment upload failed"));
  }
  const body = await response.json();
  const uploaded = (body.attachments || []).map((file, index) => ({
    ...file,
    preview: pending[index]?.preview || "",
  }));
  queuedFiles.splice(queuedFiles.length - pending.length, pending.length, ...uploaded);
  renderDraftAttachments();
  setStatus("Attachments ready.", "ready");
  files.value = "";
}

async function loadCourse(id) {
  activeCourseId = String(id);
  history.replaceState({ courseId: activeCourseId }, "", `?course=${activeCourseId}`);
  versionMode = false;
  save.disabled = false;
  showCourseControls();
  course.disabled = false;
  semester.disabled = false;
  updateVersionDisplay("");
  updateRestoreVisibility();
  resetReview();
  loading.classList.add("active");
  const response = await fetch(`/api/refined/${id}`);
  if (!response.ok) throw new Error("Unable to load course");
  const row = await response.json();
  editor.value = JSON.stringify(row.fields || {}, null, 2);
  viewer.src = yearParam(`/api/preview/course/${id}`);
  const title = row.fields?.course_title || `Course ${id}`;
  setStatus(title);
  const selected = course.querySelector(`option[value="${id}"]`);
  if (selected) selected.textContent = title;
  queuedFiles = [];
  renderDraftAttachments();
  await ensureChatSession();
  await renderMessages();
}

async function loadVersionCourse(versionId, refinedId) {
  activeCourseId = String(refinedId);
  history.replaceState({ courseId: activeCourseId }, "", `?version=${versionId}&course=${activeCourseId}`);
  versionMode = true;
  save.disabled = true;
  showCourseControls();
  course.disabled = true;
  semester.disabled = true;
  resetReview();
  loading.classList.add("active");
  const response = await fetch(`/api/versions/${versionId}/courses/${refinedId}`);
  if (!response.ok) throw new Error("Unable to load version course");
  const body = await response.json();
  editor.value = JSON.stringify(body.fields || {}, null, 2);
  viewer.src = yearParam(`/api/versions/${versionId}/courses/${refinedId}/preview`);
  updateVersionDisplay(body.version.name);
  setStatus(`${body.version.name}: ${body.fields?.course_title || `Course ${refinedId}`}`);
  queuedFiles = [];
  renderDraftAttachments();
  await ensureChatSession();
  await renderMessages();
}

async function loadVersionInEditor(versionId) {
  const response = await fetch(`/api/versions/${versionId}`);
  if (!response.ok) throw new Error("Unable to load version");
  const body = await response.json();
  const version = body.version;
  const courses = body.courses || [];
  updateVersionDisplay(version.name);
  if (!courses.length) {
    setStatus(`${version.name}: No courses in this version.`, "error");
    return;
  }
  versionMode = true;
  await loadVersionCourse(versionId, courses[0].refined_id);
}

async function loadDocumentPreview() {
  activeCourseId = "";
  activeDraftId = "";
  activeDraftRefinedId = "";
  versionMode = false;
  viewMode.value = "document";
  save.disabled = true;
  hideCourseControls();
  updateVersionDisplay("");
  updateRestoreVisibility();
  editor.value = "";
  resetReview();
  chatStatusText.textContent = "";
  loading.classList.add("active");
  viewer.src = yearParam("/api/preview/pdf");
  setStatus("Full Document");
  await ensureChatSession();
  await renderMessages();
}

async function refreshCourseDropdown() {
  const sem = semester.value;
  const entries = await courseEntries(sem);
  const prev = course.value;
  course.replaceChildren(...entries.map((c) => option(String(c.id), `${c.course_code ? c.course_code + " - " : ""}${c.course_title || "Course " + c.id}`)));
  if (prev && entries.some((c) => String(c.id) === prev)) course.value = prev;
}

async function loadCourseForReview(id) {
  activeCourseId = String(id);
  history.replaceState({ courseId: activeCourseId }, "", `?course=${activeCourseId}`);
  versionMode = false;
  save.disabled = false;
  showCourseControls();
  course.disabled = false;
  semester.disabled = false;
  updateVersionDisplay("");
  updateRestoreVisibility();
  resetReview();
  loading.classList.add("active");
  const response = await fetch(`/api/refined/${id}`);
  if (!response.ok) throw new Error("Unable to load course");
  const row = await response.json();
  const fields = row.fields || {};
  editor.value = JSON.stringify(fields, null, 2);
  viewer.src = yearParam(`/api/preview/course/${id}`);
  const title = fields.course_title || `Course ${id}`;
  setStatus(title);
  const sem = String(fields.semester || "");
  if (sem && semester.value !== sem) semester.value = sem;
  await refreshCourseDropdown();
  if (!course.querySelector(`option[value="${id}"]`)) {
    course.appendChild(option(String(id), title));
  }
  course.value = String(id);
  queuedFiles = [];
  renderDraftAttachments();
  setTab("fields");
}

async function refreshPendingCourses() {
  try {
    const response = await fetch("/api/preview/pending-courses");
    if (!response.ok) return;
    const body = await response.json();
    const courses = body.courses || [];
    pendingCourseSelect.replaceChildren(...courses.map((c) => option(String(c.id), `${c.course_code ? c.course_code + " - " : ""}${c.course_title || "Course " + c.id}`)));
  } catch {}
}

async function loadSemester(sem) {
  versionMode = false;
  save.disabled = false;
  semester.value = sem;
  course.replaceChildren();
  editor.value = "";
  viewer.removeAttribute("src");
  loading.classList.add("active");
  setStatus("Loading...");

  const entries = await courseEntries(sem);
  if (!entries.length) {
    loading.classList.remove("active");
    setStatus(`No refined courses found for Semester ${sem}.`);
    return;
  }

  course.replaceChildren(...entries.map((c) => option(String(c.id), `${c.course_code ? c.course_code + " - " : ""}${c.course_title || "Course " + c.id}`)));
  await loadCourse(String(entries[0].id));
}

chatTab.addEventListener("click", () => setTab("chat"));
fieldsTab.addEventListener("click", () => setTab("fields"));
reviewTab.addEventListener("click", () => setTab("review"));
if (togglePane) {
  togglePane.addEventListener("click", () => {
    const workspace = document.querySelector(".workspace");
    const focused = workspace.classList.toggle("chat-focus");
    togglePane.title = focused ? "Collapse agent / expand preview" : "Expand agent / collapse preview";
    togglePane.classList.toggle("active", focused);
  });
}
viewer.addEventListener("load", () => loading.classList.remove("active"));
preview.addEventListener("click", () => {
  if (viewer.src && viewer.src !== "about:blank") viewer.src = viewer.src;
});
semester.addEventListener("change", () => loadSemester(semester.value).catch(showError));
course.addEventListener("change", () => loadCourse(course.value).catch(showError));
versionSelect.addEventListener("change", () => updateRestoreVisibility());
viewMode.addEventListener("change", async () => {
  try {
    if (viewMode.value === "document") {
      await loadDocumentPreview();
      return;
    }
    showCourseControls();
    course.disabled = false;
    semester.disabled = false;
    await loadSemester(semester.value);
  } catch (error) {
    showError(error);
  }
});
attach.addEventListener("click", () => files.click());
files.addEventListener("change", () => queueFiles(files.files).catch(showError));
message.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send.click();
  }
});
saveVersion.addEventListener("click", () => saveCurrentVersion().catch((error) => {
  showError(error, "Version save failed.");
}));
restoreVersion.addEventListener("click", () => restoreSelectedVersion().catch((error) => {
  showError(error, "Version restore failed.");
}));

chatSession.addEventListener("change", async () => {
  activeSessionId = chatSession.value;
  localStorage.setItem(chatKey(), activeSessionId);
  chatLog.replaceChildren();
  chatStatusText.textContent = "Loading...";
  chatSpinner.classList.add("active");
  await renderMessages();
});

renameChat.addEventListener("click", () => enterRenameMode());
chatTitle.addEventListener("keydown", async (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    try {
      await renameActiveChat();
    } catch (error) {
      showError(error);
    }
  }
  if (e.key === "Escape") {
    exitRenameMode();
  }
});
chatTitle.addEventListener("blur", () => {
  setTimeout(() => {
    if (!chatTitle.hidden) exitRenameMode();
  }, 150);
});
deleteChat.addEventListener("click", () => deleteActiveChat().catch(showError));

newChat.addEventListener("click", async () => {
  localStorage.removeItem(chatKey());
  activeSessionId = "";
  chatLog.replaceChildren();
  await createChatSession();
  await renderMessages();
});

send.addEventListener("click", async () => {
  const content = message.value.trim();
  if (!content && !queuedFiles.length) return;
  send.disabled = true;
  if (stopBtn) stopBtn.hidden = false;
  chatStatusText.textContent = "Analyzing...";
  chatSpinner.classList.add("active");
  let assistant = null;
  const controller = new AbortController();
  activeAbortController = controller;
  try {
    await ensureChatSession();
    const attachments = queuedFiles;
    appendMessage({
      role: "user",
      content,
      attachments,
      created_at: new Date().toISOString(),
    });
    message.value = "";
    queuedFiles = [];
    renderDraftAttachments();

    const response = await fetch(`/api/chat/sessions/${activeSessionId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, metadata: { attachments } }),
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(await errorMessage(response, "Agent failed"));
    }

    let answer = "";
    await readEventStream(response, ({ event, data }) => {
      if (event === "status") {
        chatStatusText.textContent = data.message || "";
        chatSpinner.classList.add("active");
      }
      if (event === "context_usage") {
        const used = data.prompt_tokens || 0;
        const max = data.context_length || 0;
        const pct = max ? Math.round((used / max) * 100) : 0;
        const fmt = (n) => n >= 1000000 ? `${(n / 1000000).toFixed(1)}M` : `${Math.round(n / 1000)}K`;
        contextUsage.textContent = `${fmt(used)} / ${fmt(max)} (${pct}%)`;
      }
      if (event === "token") {
        if (!assistant) assistant = appendMessage({ role: "assistant", content: "", created_at: new Date().toISOString() });
        answer += data.text || "";
        renderMessageContent(assistant.content, answer);
        chatLog.scrollTop = chatLog.scrollHeight;
      }
      if (event === "tool_call") {
        const label = TOOL_LABELS[data.name] || data.name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
        chatStatusText.textContent = `${label}...`;
        const toolMsg = `\u2699 ${data.name}(${JSON.stringify(data.arguments)})`;
        const node = appendMessage({ role: "tool", content: toolMsg, created_at: new Date().toISOString() });
        node.bubble.classList.add("tool-call");
      }
      if (event === "tool_result") {
        const status = data.status === "ok" ? "\u2713" : "\u2717";
        const toolMsg = `${status} ${data.name} completed`;
        const node = appendMessage({ role: "tool", content: toolMsg, created_at: new Date().toISOString() });
        node.bubble.classList.add("tool-result");
      }
      if (event === "draft" && data.draft) {
        if (!assistant) assistant = appendMessage({ role: "assistant", content: "", created_at: new Date().toISOString() });
        if (!answer) { answer = "Draft ready for review."; renderMessageContent(assistant.content, answer); }
        showCourseDraft(data.draft);
      }
      if (event === "document_draft" && data.document_draft) {
        if (!assistant) assistant = appendMessage({ role: "assistant", content: "", created_at: new Date().toISOString() });
        if (!answer) { answer = "Document draft ready for review."; renderMessageContent(assistant.content, answer); }
        loadDocumentDraftById(data.document_draft.id).catch(showError);
      }
      if (event === "refined_course" && data.refined_id) {
        if (!assistant) assistant = appendMessage({ role: "assistant", content: "", created_at: new Date().toISOString() });
        if (!answer) { answer = data.updated ? `Updated course ${data.refined_id}. Review in Fields tab and click Save to approve.` : `Created course ${data.refined_id}. Review in Fields tab and click Save to approve.`; renderMessageContent(assistant.content, answer); }
        loadCourseForReview(data.refined_id).catch(() => {});
      }
      if (event === "error") throw new Error(data.message || "Agent failed");
      if (event === "done") {
        chatStatusText.textContent = "";
        chatSpinner.classList.remove("active");
        if (data.summary) {
          setStatus(data.summary, "ready");
        } else {
          setStatus("Response saved.", "ready");
        }
        renderMessages().catch(() => {});
      }
    });
  } catch (error) {
    const aborted = controller.signal.aborted;
    const text = aborted ? "Stopped." : (error instanceof Error ? error.message : "Agent failed");
    chatStatusText.textContent = text;
    chatSpinner.classList.remove("active");
    setStatus(text, aborted ? "" : "error");
    if (!aborted) {
      if (!assistant) assistant = appendMessage({ role: "assistant", content: "", created_at: new Date().toISOString() });
      assistant.bubble.classList.add("error");
      renderMessageContent(assistant.content, text);
    }
  } finally {
    send.disabled = false;
    if (stopBtn) stopBtn.hidden = true;
    activeAbortController = null;
  }
});

draft.addEventListener("click", async () => {
  const refinedId = activeCourseId || course.value;
  if (!refinedId || viewMode.value !== "course") return;
  setStatus("Creating draft...");
  let parsed;
  try { parsed = JSON.parse(editor.value); } catch { showError("Invalid JSON in editor. Please fix syntax errors."); return; }
  const response = await fetch("/api/agent/drafts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refined_id: Number(refinedId), fields: parsed, reason: versionMode ? "Version rollback draft" : "Live editor draft" }),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Draft failed"));
  }
  const body = await response.json();
  showCourseDraft(body.draft);
});

previewDraft.addEventListener("click", () => {
  if (activeDocumentDraftId) {
    viewer.src = yearParam(`/api/agent/document-drafts/${activeDocumentDraftId}/preview`);
    return;
  }
  if (!activeDraftId) return;
  viewer.src = yearParam(`/api/agent/drafts/${activeDraftId}/preview`);
});

applyDraft.addEventListener("click", async () => {
  if (!activeDraftId && !activeDocumentDraftId) return;
  if (!await showConfirm("Apply this draft? This will overwrite current course data.")) return;
  applyDraft.disabled = true;
  setStatus("Applying draft...");

  try {
    if (activeDocumentDraftId) {
      const response = await fetch(`/api/agent/document-drafts/${activeDocumentDraftId}/apply`, { method: "POST" });
      if (!response.ok) {
        throw new Error(await errorMessage(response, "Apply failed"));
      }
      const body = await response.json();
      if (body.version) {
        setStatus(`Document draft applied. Version: ${body.version.name}`, "ready");
        updateVersionDisplay(body.version.name);
        await refreshVersions();
      } else {
        setStatus("Document draft applied.", "ready");
      }
      await loadDocumentPreview();
      setTab("chat");
      return;
    }

    const targetId = activeDraftRefinedId || activeCourseId || course.value;
    const response = await fetch(`/api/agent/drafts/${activeDraftId}/apply`, { method: "POST" });
    if (!response.ok) {
      throw new Error(await errorMessage(response, "Apply failed"));
    }
    const body = await response.json();
    if (body.version) {
      setStatus(`Draft applied. Version: ${body.version.name}`, "ready");
      updateVersionDisplay(body.version.name);
      await refreshVersions();
    } else {
      setStatus("Draft applied.", "ready");
    }
    activeDraftId = "";
    activeDraftRefinedId = "";
    resetReview();
    if (targetId) {
      await loadCourse(targetId);
    }
    setTab("chat");
  } finally {
    applyDraft.disabled = false;
  }
});

loadDocumentDraft.addEventListener("click", () => loadDocumentDraftById(documentDraftSelect.value).catch(showError));

loadCourseDraft.addEventListener("click", () => loadCourseDraftById(courseDraftSelect.value).catch(showError));

loadPendingCourse.addEventListener("click", () => loadCourseForReview(pendingCourseSelect.value).catch(showError));

save.addEventListener("click", async () => {
  if (versionMode) return;
  const targetId = activeCourseId || course.value;
  if (!targetId) return;
  setStatus("Saving...");
  let parsed;
  try { parsed = JSON.parse(editor.value); } catch { showError("Invalid JSON in editor. Please fix syntax errors."); return; }
  const response = await fetch(`/api/refined/${targetId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields: parsed }),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Save failed"));
  }
  setStatus("Saved.", "ready");
  await refreshCourseDropdown();
  await refreshPendingCourses();
  await loadCourse(targetId);
  setTab("chat");
});

window.addEventListener("error", (event) => {
  showError(new Error(event.message));
});

window.addEventListener("unhandledrejection", (event) => {
  event.preventDefault();
  showError(event.reason);
});

const initialVersion = initialParams.get("version");
const initialCourse = initialParams.get("course") || history.state?.courseId;
let initialLoad;
if (initialVersion && initialCourse) {
  initialLoad = loadVersionCourse(initialVersion, initialCourse);
} else if (initialVersion) {
  initialLoad = loadVersionInEditor(initialVersion);
} else if (initialCourse) {
  initialLoad = loadCourse(initialCourse);
} else {
  initialLoad = loadDocumentPreview();
}

Promise.all([refreshVersions(), initialLoad]).catch(() => {
  loading.classList.remove("active");
  setStatus("Backend unavailable.", "error");
});
