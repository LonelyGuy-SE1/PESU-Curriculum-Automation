const semester = document.getElementById("semester");
const course = document.getElementById("course");
const viewMode = document.getElementById("view-mode");
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
const chatLog = document.getElementById("chat-log");
const message = document.getElementById("message");
const attach = document.getElementById("attach");
const files = document.getElementById("files");
const draftAttachments = document.getElementById("draft-attachments");
const clearChat = document.getElementById("clear-chat");
const send = document.getElementById("send");
const editor = document.getElementById("editor");
const draft = document.getElementById("draft");
const save = document.getElementById("save");
const courseDraftId = document.getElementById("course-draft-id");
const loadCourseDraft = document.getElementById("load-course-draft");
const documentDraftId = document.getElementById("document-draft-id");
const loadDocumentDraft = document.getElementById("load-document-draft");
const reviewSummary = document.getElementById("review-summary");
const diffView = document.getElementById("diff-view");
const previewDraft = document.getElementById("preview-draft");
const applyDraft = document.getElementById("apply-draft");
let activeCourseId = "";
let activeDraftId = "";
let activeSessionId = "";
let queuedFiles = [];

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
}

function chatKey() {
  return `pesu-live-editor-session:${activeCourseId || "document"}`;
}

async function ensureChatSession() {
  const key = chatKey();
  const existing = localStorage.getItem(key);
  if (existing) {
    activeSessionId = existing;
    return existing;
  }

  const response = await fetch("/api/chat/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(activeCourseId ? { refined_id: Number(activeCourseId), title: statusText.textContent } : { title: "Full Document" }),
  });
  if (!response.ok) throw new Error("Unable to create chat session");
  const body = await response.json();
  activeSessionId = String(body.session.id);
  localStorage.setItem(key, activeSessionId);
  return activeSessionId;
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

function renderMessageContent(target, value) {
  target.replaceChildren();
  const text = String(value || "");
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|https?:\/\/[^\s<>()]+)/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) target.appendChild(document.createTextNode(text.slice(last, match.index)));
    const token = match[0];
    if (token.startsWith("**")) {
      const strong = document.createElement("strong");
      strong.textContent = token.slice(2, -2);
      target.appendChild(strong);
    } else if (token.startsWith("`")) {
      const code = document.createElement("code");
      code.textContent = token.slice(1, -1);
      target.appendChild(code);
    } else {
      const link = document.createElement("a");
      const url = token.replace(/[.,;:)]}]+$/, "");
      const trailing = token.slice(url.length);
      link.href = url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = url;
      target.appendChild(link);
      if (trailing) target.appendChild(document.createTextNode(trailing));
    }
    last = match.index + token.length;
  }
  if (last < text.length) target.appendChild(document.createTextNode(text.slice(last)));
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
  statusText.textContent = "Uploading attachments...";
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
    const body = await response.json();
    throw new Error(body.detail || "Attachment upload failed");
  }
  const body = await response.json();
  const uploaded = (body.attachments || []).map((file, index) => ({
    ...file,
    preview: pending[index]?.preview || "",
  }));
  queuedFiles.splice(queuedFiles.length - pending.length, pending.length, ...uploaded);
  renderDraftAttachments();
  statusText.textContent = "Attachments ready.";
  files.value = "";
}

async function loadCourse(id) {
  activeCourseId = String(id);
  resetReview();
  loading.classList.add("active");
  const response = await fetch(`/api/refined/${id}`);
  if (!response.ok) throw new Error("Unable to load course");
  const row = await response.json();
  editor.value = JSON.stringify(row.fields || {}, null, 2);
  viewer.src = `/api/preview/course/${id}`;
  preview.href = `/api/preview/course/${id}`;
  const title = row.fields?.course_title || `Course ${id}`;
  statusText.textContent = title;
  const selected = course.querySelector(`option[value="${id}"]`);
  if (selected) selected.textContent = title;
  queuedFiles = [];
  renderDraftAttachments();
  await ensureChatSession();
  await renderMessages();
}

async function loadDocumentPreview() {
  activeCourseId = "";
  activeDraftId = "";
  course.disabled = true;
  semester.disabled = true;
  editor.value = "";
  resetReview();
  loading.classList.add("active");
  viewer.src = "/api/preview/pdf";
  preview.href = "/api/preview/pdf";
  statusText.textContent = "Full Document";
  await ensureChatSession();
  await renderMessages();
}

async function loadSemester(sem) {
  semester.value = sem;
  course.replaceChildren();
  editor.value = "";
  viewer.removeAttribute("src");
  preview.removeAttribute("href");
  loading.classList.add("active");
  statusText.textContent = "Loading...";

  const ids = await courseIds(sem);
  if (!ids.length) {
    loading.classList.remove("active");
    statusText.textContent = `No refined courses found for Semester ${sem}.`;
    return;
  }

  ids.forEach((id) => {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = `Course ${id}`;
    course.appendChild(option);
  });
  await loadCourse(ids[0]);
}

chatTab.addEventListener("click", () => setTab("chat"));
fieldsTab.addEventListener("click", () => setTab("fields"));
reviewTab.addEventListener("click", () => setTab("review"));
viewer.addEventListener("load", () => loading.classList.remove("active"));
semester.addEventListener("change", () => loadSemester(semester.value));
course.addEventListener("change", () => loadCourse(course.value));
viewMode.addEventListener("change", async () => {
  if (viewMode.value === "document") {
    await loadDocumentPreview();
    return;
  }
  course.disabled = false;
  semester.disabled = false;
  await loadSemester(semester.value);
});
attach.addEventListener("click", () => files.click());
files.addEventListener("change", () => queueFiles(files.files));

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
    assistant = appendMessage({ role: "assistant", content: "", created_at: new Date().toISOString() });
    message.value = "";
    queuedFiles = [];
    renderDraftAttachments();

    const response = await fetch(`/api/chat/sessions/${activeSessionId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, metadata: { attachments } }),
    });
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.detail || "Chat failed");
    }

    let answer = "";
    await readEventStream(response, ({ event, data }) => {
      if (event === "status") statusText.textContent = data.message || "";
      if (event === "token") {
        answer += data.text || "";
        renderMessageContent(assistant.content, answer);
        chatLog.scrollTop = chatLog.scrollHeight;
      }
      if (event === "error") throw new Error(data.message || "Chat failed");
      if (event === "done") statusText.textContent = "Response saved.";
    });
  } catch (error) {
    const text = error instanceof Error ? error.message : "Chat failed";
    statusText.textContent = text;
    if (assistant) {
      renderMessageContent(assistant.content, text);
    } else {
      appendMessage({ role: "assistant", content: text, created_at: new Date().toISOString() });
    }
  } finally {
    send.disabled = false;
  }
});

clearChat.addEventListener("click", async () => {
  localStorage.removeItem(chatKey());
  activeSessionId = "";
  chatLog.replaceChildren();
  await ensureChatSession();
});

draft.addEventListener("click", async () => {
  if (!course.value || viewMode.value !== "course") return;
  statusText.textContent = "Creating draft...";
  const parsed = JSON.parse(editor.value);
  const response = await fetch("/api/agent/drafts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refined_id: Number(course.value), fields: parsed, reason: "Live editor draft" }),
  });
  if (!response.ok) {
    const body = await response.json();
    throw new Error(body.detail || "Draft failed");
  }
  const body = await response.json();
  renderDraftReview(body.draft);
  viewer.src = `/api/agent/drafts/${body.draft.id}/preview`;
  preview.href = `/api/agent/drafts/${body.draft.id}/preview`;
  statusText.textContent = "Draft ready for review.";
  setTab("review");
});

previewDraft.addEventListener("click", () => {
  if (!activeDraftId) return;
  viewer.src = `/api/agent/drafts/${activeDraftId}/preview`;
  preview.href = `/api/agent/drafts/${activeDraftId}/preview`;
});

applyDraft.addEventListener("click", async () => {
  if (!activeDraftId) return;
  statusText.textContent = "Applying draft...";
  const response = await fetch(`/api/agent/drafts/${activeDraftId}/apply`, { method: "POST" });
  if (!response.ok) {
    const body = await response.json();
    throw new Error(body.detail || "Apply failed");
  }
  await loadCourse(course.value);
  statusText.textContent = "Draft applied.";
});

loadDocumentDraft.addEventListener("click", async () => {
  const id = documentDraftId.value.trim();
  if (!id) return;
  statusText.textContent = "Loading document draft...";
  const response = await fetch(`/api/agent/document-drafts/${id}`);
  if (!response.ok) {
    const body = await response.json();
    throw new Error(body.detail || "Document draft not found");
  }
  const body = await response.json();
  const summary = body.document_draft.diff_summary || {};
  activeDraftId = "";
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
  previewDraft.disabled = true;
  applyDraft.disabled = true;
  viewer.src = `/api/agent/document-drafts/${id}/preview`;
  preview.href = `/api/agent/document-drafts/${id}/preview`;
});

loadCourseDraft.addEventListener("click", async () => {
  const id = courseDraftId.value.trim();
  if (!id) return;
  statusText.textContent = "Loading course draft...";
  const response = await fetch(`/api/agent/drafts/${id}`);
  if (!response.ok) {
    const body = await response.json();
    throw new Error(body.detail || "Course draft not found");
  }
  const body = await response.json();
  renderDraftReview(body.draft);
  viewer.src = `/api/agent/drafts/${id}/preview`;
  preview.href = `/api/agent/drafts/${id}/preview`;
  statusText.textContent = "Course draft loaded.";
});

save.addEventListener("click", async () => {
  statusText.textContent = "Saving...";
  const parsed = JSON.parse(editor.value);
  const response = await fetch(`/api/refined/${course.value}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields: parsed }),
  });
  if (!response.ok) {
    const body = await response.json();
    throw new Error(body.detail || "Save failed");
  }
  await loadCourse(course.value);
  setTab("chat");
});

window.addEventListener("error", (event) => {
  loading.classList.remove("active");
  statusText.textContent = event.message;
});

firstAvailableSemester().then(loadSemester).catch(() => {
  loading.classList.remove("active");
  statusText.textContent = "Backend unavailable.";
});
