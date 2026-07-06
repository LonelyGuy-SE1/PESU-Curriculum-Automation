const version = document.getElementById("version");
const course = document.getElementById("course");
const openEditor = document.getElementById("open-editor");
const previewLink = document.getElementById("preview-link");
const snapshotForm = document.getElementById("snapshot-form");
const versionName = document.getElementById("version-name");
const academicYear = document.getElementById("academic-year");
const statusText = document.getElementById("status");
const viewer = document.getElementById("viewer");

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
  const year = item.academic_year ? ` ${item.academic_year}` : "";
  return `${item.name}${year}`;
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
    statusText.textContent = "No versions saved.";
    return;
  }
  await loadVersion();
}

async function loadVersion() {
  const body = await json(`/api/versions/${version.value}`);
  course.replaceChildren(...(body.courses || []).map((item) => option(item.refined_id, courseLabel(item))));
  previewLink.href = `/api/versions/${version.value}/preview`;
  viewer.src = previewLink.href;
  statusText.textContent = body.courses?.length ? "Version loaded." : "Version has no courses.";
}

version.addEventListener("change", loadVersion);

course.addEventListener("change", () => {
  if (!course.value) return;
  viewer.src = `/api/versions/${version.value}/courses/${course.value}/preview`;
});

openEditor.addEventListener("click", () => {
  if (!version.value || !course.value) return;
  location.href = `../live-editor/?version=${encodeURIComponent(version.value)}&course=${encodeURIComponent(course.value)}`;
});

snapshotForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  statusText.textContent = "Saving version...";
  await json("/api/versions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: versionName.value, academic_year: academicYear.value }),
  });
  versionName.value = "";
  academicYear.value = "";
  statusText.textContent = "Version saved.";
  await loadVersions();
});

loadVersions().catch((error) => {
  statusText.textContent = error instanceof Error ? error.message : "Unable to load versions.";
});
