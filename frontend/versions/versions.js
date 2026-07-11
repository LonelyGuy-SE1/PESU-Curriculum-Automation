const version = document.getElementById("version");
const openEditor = document.getElementById("open-editor");
const snapshotForm = document.getElementById("snapshot-form");
const versionName = document.getElementById("version-name");
const statusText = document.getElementById("status");
const viewer = document.getElementById("viewer");

function setStatus(text, kind = "") {
  statusText.textContent = text || "";
  statusText.className = kind;
  statusText.hidden = !text;
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

async function loadVersions() {
  const body = await json("/api/versions");
  version.replaceChildren(...(body.versions || []).map((item) => option(item.id, item.name || `Snapshot ${item.id}`)));
  setStatus(body.versions?.length ? "Select a version to preview." : "No snapshots saved.");
  viewer.src = "/api/preview/pdf";
}

version.addEventListener("change", () => {
  if (!version.value) return;
  viewer.src = `/api/versions/${version.value}/preview`;
  setStatus(`Viewing snapshot ${version.value}`);
});

openEditor.addEventListener("click", () => {
  if (!version.value) return;
  location.href = `../live-editor/?version=${encodeURIComponent(version.value)}&course=1`;
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
