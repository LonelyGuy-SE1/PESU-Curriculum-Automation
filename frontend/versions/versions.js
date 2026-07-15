const statusText = document.getElementById("status");
const viewer = document.getElementById("viewer");
const versionList = document.getElementById("version-list");
const openEditor = document.getElementById("open-editor");

function setStatus(text, kind = "") {
  statusText.textContent = text || "";
  statusText.className = kind;
  statusText.hidden = !text;
}

function icon(name) {
  const icons = {
    chevron: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>',
    folder: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>',
    tag: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path><line x1="7" y1="7" x2="7.01" y2="7"></line></svg>',
    edit: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
  };
  return icons[name] || "";
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  return new Date(dateStr).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function groupVersions(versions) {
  const groups = new Map();
  for (const v of versions) {
    const year = v.academic_year || "Uncategorized";
    if (!groups.has(year)) groups.set(year, []);
    groups.get(year).push(v);
  }
  return [...groups.entries()].sort((a, b) => b[0].localeCompare(a[0]));
}

let activeVersionId = null;

function renderVersionTree(groups) {
  versionList.replaceChildren();
  if (!groups.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No snapshots saved. Create one from the Live Editor.";
    versionList.appendChild(empty);
    return;
  }

  for (const [year, versions] of groups) {
    const group = document.createElement("div");
    group.className = "tree-group";

    const header = document.createElement("div");
    header.className = "tree-group-header";
    header.innerHTML = `<span class="expand-icon">${icon("chevron")}</span><span class="folder-icon">${icon("folder")}</span><span class="group-label">${year}</span><span class="version-count">${versions.length}</span>`;
    header.addEventListener("click", () => group.classList.toggle("collapsed"));

    const items = document.createElement("div");
    items.className = "tree-items";

    for (const v of versions) {
      const item = document.createElement("div");
      item.className = "tree-item";
      if (String(v.id) === String(activeVersionId)) item.classList.add("active");
      item.dataset.versionId = v.id;

      const info = document.createElement("div");
      info.className = "item-info";

      const nameRow = document.createElement("div");
      nameRow.className = "item-name";
      nameRow.textContent = v.name || `Snapshot ${v.id}`;

      const meta = document.createElement("div");
      meta.className = "item-meta";
      meta.textContent = `${formatDate(v.created_at)}${v.status ? ` \u2022 ${v.status}` : ""}`;

      info.append(nameRow, meta);

      const editBtn = document.createElement("button");
      editBtn.className = "icon-btn edit-btn";
      editBtn.title = "Edit name / category";
      editBtn.innerHTML = icon("edit");
      editBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        startEdit(v, item);
      });

      item.append(info, editBtn);
      item.addEventListener("click", (e) => {
        if (e.target.closest(".edit-btn")) return;
        loadVersion(v.id);
      });
      items.appendChild(item);
    }

    group.append(header, items);
    versionList.appendChild(group);
  }
}

function startEdit(v, itemEl) {
  const existing = itemEl.querySelector(".edit-form");
  if (existing) { existing.remove(); return; }

  const form = document.createElement("div");
  form.className = "edit-form";

  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.value = v.name || "";
  nameInput.placeholder = "Version name";

  const yearInput = document.createElement("input");
  yearInput.type = "text";
  yearInput.value = v.academic_year || "";
  yearInput.placeholder = "Category (e.g. 2025-2026)";

  const actions = document.createElement("div");
  actions.className = "edit-actions";

  const saveBtn = document.createElement("button");
  saveBtn.className = "primary";
  saveBtn.textContent = "Save";
  saveBtn.addEventListener("click", () => saveEdit(v.id, nameInput.value, yearInput.value, form));

  const cancelBtn = document.createElement("button");
  cancelBtn.textContent = "Cancel";
  cancelBtn.addEventListener("click", () => form.remove());

  actions.append(saveBtn, cancelBtn);
  form.append(nameInput, yearInput, actions);
  itemEl.appendChild(form);
  nameInput.focus();
}

async function saveEdit(versionId, name, academicYear, formEl) {
  try {
    const res = await fetch(`/api/versions/${versionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), academic_year: academicYear.trim() }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Update failed");
    formEl.remove();
    setStatus("Updated.", "ready");
    await loadVersions();
  } catch (e) {
    setStatus(e.message, "error");
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
  activeVersionId = String(versionId);
  versionList.querySelectorAll(".tree-item").forEach((el) => el.classList.toggle("active", el.dataset.versionId === String(versionId)));
  viewer.src = `/api/versions/${versionId}/preview?diff=1&_t=${Date.now()}`;
  openEditor.href = `/live-editor/?version=${versionId}`;
  openEditor.hidden = false;
  setStatus(`Viewing diff for snapshot ${versionId}`);
}

loadVersions().catch(() => setStatus("Failed to load versions.", "error"));
