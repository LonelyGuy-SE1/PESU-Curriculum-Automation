const snapshotForm = document.getElementById("snapshot-form");
const versionName = document.getElementById("version-name");
const statusText = document.getElementById("status");
const viewer = document.getElementById("viewer");
const versionList = document.getElementById("version-list");

function setStatus(text, kind = "") {
  statusText.textContent = text || "";
  statusText.className = kind;
  statusText.hidden = !text;
}

function icon(name) {
  const icons = {
    chevron: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>',
    clock: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>',
    tag: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path><line x1="7" y1="7" x2="7.01" y2="7"></line></svg>',
    folder: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>',
  };
  return icons[name] || "";
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function versionLabel(v) {
  const parts = [];
  if (v.name) parts.push(v.name);
  if (v.created_at) parts.push(formatDate(v.created_at));
  return parts.join(" — ") || `Snapshot ${v.id}`;
}

function groupVersions(versions) {
  const groups = new Map();
  for (const v of versions) {
    const year = v.academic_year || "Uncategorized";
    if (!groups.has(year)) groups.set(year, []);
    groups.get(year).push(v);
  }
  const sorted = [...groups.entries()].sort((a, b) => b[0].localeCompare(a[0]));
  return sorted;
}

function renderVersionTree(groups) {
  versionList.replaceChildren();
  if (!groups.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No snapshots saved.";
    versionList.appendChild(empty);
    return;
  }

  for (const [year, versions] of groups) {
    const group = document.createElement("div");
    group.className = "tree-group";

    const header = document.createElement("div");
    header.className = "tree-group-header";
    header.innerHTML = `
      <span class="expand-icon">${icon("chevron")}</span>
      <span class="folder-icon">${icon("folder")}</span>
      <span>${year}</span>
      <span class="version-count">${versions.length} snapshot${versions.length !== 1 ? "s" : ""}</span>
    `;
    header.addEventListener("click", () => group.classList.toggle("collapsed"));

    const items = document.createElement("div");
    items.className = "tree-items";

    for (const v of versions) {
      const item = document.createElement("div");
      item.className = "tree-item";
      item.dataset.versionId = v.id;
      item.innerHTML = `
        <span class="item-icon">${icon("tag")}</span>
        <div class="item-info">
          <div class="item-name">${v.name || `Snapshot ${v.id}`}</div>
          <div class="item-meta">${formatDate(v.created_at)}${v.status ? ` • ${v.status}` : ""}</div>
        </div>
      `;
      item.addEventListener("click", (e) => {
        e.stopPropagation();
        loadVersion(v.id);
      });
      items.appendChild(item);
    }

    group.append(header, items);
    versionList.appendChild(group);
  }
}

async function loadVersions() {
  try {
    const res = await fetch("/api/versions");
    if (!res.ok) throw new Error("Failed to load versions");
    const body = await res.json();
    const groups = groupVersions(body.versions || []);
    renderVersionTree(groups);
    setStatus(body.versions?.length ? "Select a version to preview diff." : "No snapshots saved.");
  } catch (e) {
    setStatus(e.message, "error");
  }
}

function loadVersion(versionId) {
  versionList.querySelectorAll(".tree-item").forEach((el) => el.classList.toggle("active", el.dataset.versionId === versionId));
  viewer.src = `/api/versions/${versionId}/preview?diff=1`;
  setStatus(`Viewing diff for snapshot ${versionId}`);
}

async function saveSnapshot() {
  const name = versionName.value.trim();
  if (!name) {
    setStatus("Snapshot name required.", "error");
    return;
  }
  setStatus("Saving snapshot...");
  try {
    const res = await fetch("/api/versions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Save failed");
    versionName.value = "";
    setStatus("Snapshot saved.", "ready");
    await loadVersions();
  } catch (e) {
    setStatus(e.message, "error");
  }
}

snapshotForm.addEventListener("submit", (e) => {
  e.preventDefault();
  saveSnapshot();
});

loadVersions().catch(() => setStatus("Failed to load versions.", "error"));