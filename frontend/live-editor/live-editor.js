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
const message = document.getElementById("message");
const attach = document.getElementById("attach");
const files = document.getElementById("files");
const draftAttachments = document.getElementById("draft-attachments");
const send = document.getElementById("send");
const editor = document.getElementById("editor");
const draft = document.getElementById("draft");
const save = document.getElementById("save");
const courseDraftSelect = document.getElementById("course-draft-select");
const loadCourseDraft = document.getElementById("load-course-draft");
const documentDraftSelect = document.getElementById("document-draft-select");
const loadDocumentDraft = document.getElementById("load-document-draft");
const reviewSummary = document.getElementById("review-summary");
const diffView = document.getElementById("diff-view");
const previewDraft = document.getElementById("preview-draft");
const applyDraft = document.getElementById("apply-draft");
let activeCourseId = "";
let activeDraftId = "";
let activeDocumentDraftId = "";
let activeSessionId = "";
let queuedFiles = [];
let versionMode = false;
const initialParams = new URLSearchParams(location.search);

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
    body: JSON.stringify(activeCourseId ? { refined_id: Number(activeCourseId), title: statusText.textContent } : { title: "Full Document" }),
  });
  if (!response.ok) throw new Error("Unable to create chat session");
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
  if (!confirm("Delete this chat thread permanently?")) return;
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
    visual.textContent = "FILE";
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
  if (removable) {
    const remove = document.createElement("button");
    remove.className = "attachment-remove";
    remove.type = "button";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => {
      queuedFiles.splice(index, 1);
      renderDraftAttachments();
    });
    item.appendChild(remove);
  } else {
    item.appendChild(document.createElement("span"));
  }
  return item;
}

function renderDraftAttachments() {
  draftAttachments.replaceChildren(...queuedFiles.map((file, index) => attachmentNode(file, index, true)));
}

function messageNode(item) {
  const bubble = document.createElement("div");
  bubble.className = `message ${item.role}`;
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
  const messages = await loadMessages();
  chatLog.replaceChildren();
  messages.forEach((item) => appendMessage(item));
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
      if (raw) onEvent(parseEvent(raw));
      index = buffer.indexOf("\n\n");
    }
  }
}

function resetReview() {
  activeDraftId = "";
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
  viewer.src = `/api/agent/drafts/${draftRow.id}/preview?diff=1`;
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
  viewer.src = `/api/agent/document-drafts/${id}/preview?diff=1`;
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
  versionMode = false;
  save.disabled = false;
  course.disabled = false;
  semester.disabled = false;
  resetReview();
  loading.classList.add("active");
  const response = await fetch(`/api/refined/${id}`);
  if (!response.ok) throw new Error("Unable to load course");
  const row = await response.json();
  editor.value = JSON.stringify(row.fields || {}, null, 2);
  viewer.src = `/api/preview/course/${id}`;
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
  versionMode = true;
  save.disabled = true;
  course.disabled = true;
  semester.disabled = true;
  resetReview();
  loading.classList.add("active");
  const response = await fetch(`/api/versions/${versionId}/courses/${refinedId}`);
  if (!response.ok) throw new Error("Unable to load version course");
  const body = await response.json();
  editor.value = JSON.stringify(body.fields || {}, null, 2);
  viewer.src = `/api/versions/${versionId}/courses/${refinedId}/preview`;
  setStatus(`${body.version.name}: ${body.fields?.course_title || `Course ${refinedId}`}`);
  queuedFiles = [];
  renderDraftAttachments();
  await ensureChatSession();
  await renderMessages();
}

async function loadDocumentPreview() {
  activeCourseId = "";
  activeDraftId = "";
  versionMode = false;
  viewMode.value = "document";
  save.disabled = true;
  course.disabled = true;
  semester.disabled = true;
  editor.value = "";
  resetReview();
  chatStatus.textContent = "";
  viewer.src = "/api/preview/pdf";
  setStatus("Full Document");
  await ensureChatSession();
  await renderMessages();
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

  const ids = await courseIds(sem);
  if (!ids.length) {
    loading.classList.remove("active");
    setStatus(`No refined courses found for Semester ${sem}.`);
    return;
  }

  course.replaceChildren(...ids.map((id) => option(id, `Course ${id}`)));
  await loadCourse(ids[0]);
}

chatTab.addEventListener("click", () => setTab("chat"));
fieldsTab.addEventListener("click", () => setTab("fields"));
reviewTab.addEventListener("click", () => setTab("review"));
viewer.addEventListener("load", () => loading.classList.remove("active"));
preview.addEventListener("click", () => {
  if (viewer.src && viewer.src !== "about:blank") viewer.src = viewer.src;
});
semester.addEventListener("change", () => loadSemester(semester.value).catch(showError));
course.addEventListener("change", () => loadCourse(course.value).catch(showError));
viewMode.addEventListener("change", async () => {
  try {
    if (viewMode.value === "document") {
      await loadDocumentPreview();
      return;
    }
    course.disabled = false;
    semester.disabled = false;
    await loadSemester(semester.value);
  } catch (error) {
    showError(error);
  }
});
attach.addEventListener("click", () => files.click());
files.addEventListener("change", () => queueFiles(files.files).catch(showError));
saveVersion.addEventListener("click", () => saveCurrentVersion().catch((error) => {
  showError(error, "Version save failed.");
}));
restoreVersion.addEventListener("click", () => restoreSelectedVersion().catch((error) => {
  showError(error, "Version restore failed.");
}));

chatSession.addEventListener("change", async () => {
  activeSessionId = chatSession.value;
  localStorage.setItem(chatKey(), activeSessionId);
  await refreshChatSessions();
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
  let assistant = null;
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
    });
    if (!response.ok) {
      throw new Error(await errorMessage(response, "Chat failed"));
    }

    let answer = "";
    await readEventStream(response, ({ event, data }) => {
      if (event === "status") { chatStatus.textContent = data.message || ""; }
      if (event === "token") {
        if (!assistant) assistant = appendMessage({ role: "assistant", content: "", created_at: new Date().toISOString() });
        answer += data.text || "";
        renderMessageContent(assistant.content, answer);
        chatLog.scrollTop = chatLog.scrollHeight;
      }
      if (event === "draft" && data.draft) {
        if (!assistant) assistant = appendMessage({ role: "assistant", content: "", created_at: new Date().toISOString() });
        if (!answer) renderMessageContent(assistant.content, "Draft ready for review.");
        showCourseDraft(data.draft);
      }
      if (event === "document_draft" && data.document_draft) {
        if (!assistant) assistant = appendMessage({ role: "assistant", content: "", created_at: new Date().toISOString() });
        if (!answer) renderMessageContent(assistant.content, "Document draft ready for review.");
        loadDocumentDraftById(data.document_draft.id).catch(showError);
      }
      if (event === "error") throw new Error(data.message || "Chat failed");
      if (event === "done") { chatStatus.textContent = ""; setStatus("Response saved.", "ready"); }
    });
  } catch (error) {
    const text = error instanceof Error ? error.message : "Chat failed";
    chatStatus.textContent = text;
    setStatus(text, "error");
    if (assistant) {
      assistant.bubble.classList.add("error");
      renderMessageContent(assistant.content, text);
    }
  } finally {
    send.disabled = false;
  }
});

draft.addEventListener("click", async () => {
  const refinedId = activeCourseId || course.value;
  if (!refinedId || viewMode.value !== "course") return;
  setStatus("Creating draft...");
  const parsed = JSON.parse(editor.value);
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
    viewer.src = `/api/agent/document-drafts/${activeDocumentDraftId}/preview`;
    return;
  }
  if (!activeDraftId) return;
  viewer.src = `/api/agent/drafts/${activeDraftId}/preview`;
});

applyDraft.addEventListener("click", async () => {
  if (!activeDraftId && !activeDocumentDraftId) return;
  setStatus("Applying draft...");

  if (activeDocumentDraftId) {
    const response = await fetch(`/api/agent/document-drafts/${activeDocumentDraftId}/apply`, { method: "POST" });
    if (!response.ok) {
      throw new Error(await errorMessage(response, "Apply failed"));
    }
    await loadDocumentDraftById(activeDocumentDraftId);
    setStatus("Document draft applied.", "ready");
    return;
  }

  const response = await fetch(`/api/agent/drafts/${activeDraftId}/apply`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Apply failed"));
  }
  await loadCourse(activeCourseId || course.value);
  setStatus("Draft applied.", "ready");
});

loadDocumentDraft.addEventListener("click", () => loadDocumentDraftById(documentDraftSelect.value).catch(showError));

loadCourseDraft.addEventListener("click", () => loadCourseDraftById(courseDraftSelect.value).catch(showError));

save.addEventListener("click", async () => {
  if (versionMode) return;
  setStatus("Saving...");
  const parsed = JSON.parse(editor.value);
  const response = await fetch(`/api/refined/${activeCourseId || course.value}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields: parsed }),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Save failed"));
  }
  await loadCourse(course.value);
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
const initialCourse = initialParams.get("course");
const initialLoad = initialVersion && initialCourse ? loadVersionCourse(initialVersion, initialCourse) : loadDocumentPreview();

Promise.all([refreshVersions(), initialLoad]).catch(() => {
  loading.classList.remove("active");
  setStatus("Backend unavailable.", "error");
});
