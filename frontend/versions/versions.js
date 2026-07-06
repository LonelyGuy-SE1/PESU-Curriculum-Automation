const version = document.getElementById("version");
const course = document.getElementById("course");
const previewVersion = document.getElementById("preview-version");
const openEditor = document.getElementById("open-editor");
const previewLink = document.getElementById("preview-link");
const snapshotForm = document.getElementById("snapshot-form");
const versionName = document.getElementById("version-name");
const statusText = document.getElementById("status");
const viewer = document.getElementById("viewer");

function setStatus(text, kind = "") {
  statusText.textContent = text || "";
  statusText.className = `status-line ${kind}`.trim();
}

function option(value, text) {
  const item = document.createElement("option");
  item.value = value;
  item.textContent = text;
  return item;
}

async function json(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || "Request failed");
  return body;
}

function versionLabel(item) {
  return item.name || `Snapshot ${item.id}`;
}

function courseLabel(item) {
  const code = item.course_code ? `${item.course_code} - ` : "";
  const sem = item.semester ? `S${item.semester} ` : "";
  return `${sem}${code}${item.course_title || `Course ${item.refined_id}`}`;
}

async function loadVersions() {
  const body = await json("/api/versions");
  version.replaceChildren(...(body.versions || []).map((item) => option(item.id, versionLabel(item))));
  if (!version.value) {
    setStatus("No snapshots saved.");
    return;
  }
  await loadVersion();
}

async function loadVersion() {
  const body = await json(`/api/versions/${version.value}`);
  course.replaceChildren(...(body.courses || []).map((item) => option(item.refined_id, courseLabel(item))));
  showVersionPreview();
  setStatus(body.courses?.length ? `${body.courses.length} courses in snapshot.` : "Snapshot has no courses.", body.courses?.length ? "ready" : "");
}

function showVersionPreview() {
  if (!version.value) return;
  previewLink.href = `/api/versions/${version.value}/preview`;
  viewer.src = previewLink.href;
}

function showCoursePreview() {
  if (!version.value || !course.value) return;
  previewLink.href = `/api/versions/${version.value}/courses/${course.value}/preview`;
  viewer.src = previewLink.href;
}

version.addEventListener("change", loadVersion);
previewVersion.addEventListener("click", showVersionPreview);

course.addEventListener("change", () => {
  showCoursePreview();
});

openEditor.addEventListener("click", () => {
  if (!version.value || !course.value) return;
  location.href = `../live-editor/?version=${encodeURIComponent(version.value)}&course=${encodeURIComponent(course.value)}`;
});

snapshotForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("Saving snapshot...");
  await json("/api/versions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: versionName.value }),
  });
  versionName.value = "";
  setStatus("Snapshot saved.", "ready");
  await loadVersions();
});

loadVersions().catch((error) => {
  setStatus(error instanceof Error ? error.message : "Unable to load versions.", "error");
});
