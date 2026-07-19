const statusText = document.getElementById("status");
const viewer = document.getElementById("viewer");
const versionList = document.getElementById("version-list");
const openEditor = document.getElementById("open-editor");
const viewerLoading = document.getElementById("viewer-loading");
const emptyState = document.getElementById("empty-state");
const sidebar = document.getElementById("sidebar");
const sidebarOverlay = document.getElementById("sidebar-overlay");
const mobileMenuBtn = document.getElementById("mobile-menu");
const toggleGroupsBtn = document.getElementById("toggle-groups");
const showEmptyToggle = document.getElementById("show-empty");
const baseVersionSelect = document.getElementById("base-version");
const compareVersionSelect = document.getElementById("compare-version");
const compareBtn = document.getElementById("compare-btn");

function setStatus(text, kind = "") {
  statusText.textContent = text || "";
  statusText.className = kind;
  statusText.hidden = !text;
}

function icon(name) {
  const icons = {
    chevron: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>',
    folder: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>',
    edit: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
    trash: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
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
    empty.textContent = "No snapshots saved. Create one from the Agentic Editor.";
    versionList.appendChild(empty);
    return;
  }

  for (const [year, versions] of groups) {
    const group = document.createElement("div");
    group.className = "tree-group";

    const header = document.createElement("div");
    header.className = "tree-group-header";
    header.tabIndex = 0;
    header.role = "button";
    header.setAttribute("aria-expanded", "true");

    const expandIcon = document.createElement("span");
    expandIcon.className = "expand-icon";
    expandIcon.innerHTML = icon("chevron");

    const folderIcon = document.createElement("span");
    folderIcon.className = "folder-icon";
    folderIcon.innerHTML = icon("folder");

    const label = document.createElement("span");
    label.className = "group-label";
    label.textContent = year;

    const count = document.createElement("span");
    count.className = "version-count";
    count.textContent = String(versions.length);

    const groupEditBtn = document.createElement("button");
    groupEditBtn.className = "icon-btn group-edit-btn";
    groupEditBtn.title = "Rename category";
    groupEditBtn.innerHTML = icon("edit");
    groupEditBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      startGroupEdit(year, versions, label, groupEditBtn);
    });

    header.append(expandIcon, folderIcon, label, count, groupEditBtn);

    const toggleGroup = () => {
      const collapsed = group.classList.toggle("collapsed");
      header.setAttribute("aria-expanded", String(!collapsed));
    };
    header.addEventListener("click", toggleGroup);
    header.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleGroup(); }
    });

    const items = document.createElement("div");
    items.className = "tree-items";

    for (const v of versions) {
      const item = document.createElement("div");
      item.className = "tree-item";
      item.tabIndex = 0;
      item.role = "button";
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

      const deleteBtn = document.createElement("button");
      deleteBtn.className = "icon-btn delete-btn";
      deleteBtn.title = "Delete version";
      deleteBtn.innerHTML = icon("trash");
      deleteBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteVersion(v.id, v.name || `Version ${v.id}`);
      });

      item.append(info, editBtn, deleteBtn);

      const activate = (e) => {
        if (e.target.closest(".edit-btn") || e.target.closest(".delete-btn")) return;
        loadVersion(v.id);
      };
      item.addEventListener("click", activate);
      item.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activate(e); }
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
  nameInput.maxLength = 200;

  const yearInput = document.createElement("input");
  yearInput.type = "text";
  yearInput.value = v.academic_year || "";
  yearInput.placeholder = "Category (e.g. 2025-2026)";
  yearInput.maxLength = 50;

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
  const trimmedName = name.trim();
  if (!trimmedName) {
    setStatus("Version name cannot be empty.", "error");
    return;
  }
  try {
    const res = await fetch(`/api/versions/${versionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: trimmedName, academic_year: academicYear.trim() }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Update failed");
    formEl.remove();
    setStatus("Updated.", "ready");
    await loadVersions();
  } catch (e) {
    setStatus(e.message, "error");
  }
}

async function deleteVersion(versionId, name) {
  if (!await showConfirm(`Delete "${name}"? This cannot be undone.`)) return;
  try {
    const res = await fetch(`/api/versions/${versionId}`, { method: "DELETE" });
    if (!res.ok) throw new Error((await res.json()).detail || "Delete failed");
    if (String(activeVersionId) === String(versionId)) {
      activeVersionId = null;
      viewer.src = "";
      emptyState.hidden = false;
      viewer.hidden = true;
      openEditor.hidden = true;
    }
    setStatus("Deleted.", "ready");
    await loadVersions();
  } catch (e) {
    setStatus(e.message, "error");
  }
}

function startGroupEdit(year, versions, labelEl, btnEl) {
  if (labelEl.querySelector("input")) return;
  const prevText = labelEl.textContent;
  const input = document.createElement("input");
  input.type = "text";
  input.value = year;
  input.maxLength = 50;
  input.style.cssText = "width:100%;height:24px;font:inherit;font-size:12px;padding:0 4px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--background);color:var(--foreground);outline:none;";
  labelEl.textContent = "";
  labelEl.appendChild(input);
  input.focus();
  input.select();

  const finish = async (save) => {
    const newVal = input.value.trim();
    input.remove();
    if (!save || newVal === year || !newVal) {
      labelEl.textContent = prevText;
      return;
    }
    const ids = versions.map((v) => v.id);
    try {
      for (const id of ids) {
        const res = await fetch(`/api/versions/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ academic_year: newVal }),
        });
        if (!res.ok) throw new Error((await res.json()).detail || "Update failed");
      }
      setStatus("Category renamed.", "ready");
      await loadVersions();
    } catch (e) {
      setStatus(e.message, "error");
      labelEl.textContent = prevText;
    }
  };

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") finish(true);
    if (e.key === "Escape") finish(false);
  });
  input.addEventListener("blur", () => finish(true));
}

let allVersions = [];

async function loadVersions() {
  setStatus("Loading versions...");
  try {
    const res = await fetch("/api/versions");
    if (!res.ok) throw new Error("Failed to load versions");
    const body = await res.json();
    allVersions = body.versions || [];
    renderFilteredVersions();
    populateCompareSelects();
  } catch (e) {
    setStatus(e.message, "error");
  }
}

function renderFilteredVersions() {
  const showEmpty = showEmptyToggle && showEmptyToggle.checked;
  const filtered = showEmpty ? allVersions : allVersions.filter((v) => (v.course_count || 0) > 0 && v.has_changes !== false);
  const groups = groupVersions(filtered);
  renderVersionTree(groups);
  if (!filtered.length) {
    setStatus(allVersions.length ? "No versions with changes." : "No snapshots saved.", "ready");
  } else {
    setStatus("Select a version to preview diff.", "ready");
  }
}

function populateCompareSelects() {
  const options = allVersions.map((v) => `<option value="${v.id}">${v.name || `Snapshot ${v.id}`}</option>`).join("");
  const placeholder = '<option value="">Select version</option>';
  baseVersionSelect.innerHTML = placeholder + options;
  compareVersionSelect.innerHTML = placeholder + options;
}

if (compareBtn) {
  compareBtn.addEventListener("click", () => {
    const id1 = baseVersionSelect.value;
    const id2 = compareVersionSelect.value;
    if (!id1 || !id2) {
      setStatus("Select both versions to compare.", "error");
      return;
    }
    if (id1 === id2) {
      setStatus("Select two different versions.", "error");
      return;
    }
    const v1 = allVersions.find((v) => String(v.id) === id1);
    const v2 = allVersions.find((v) => String(v.id) === id2);
    emptyState.hidden = true;
    viewerLoading.hidden = false;
    viewer.hidden = true;

    const onLoad = () => {
      viewerLoading.hidden = true;
      viewer.hidden = false;
      viewer.removeEventListener("load", onLoad);
    };
    viewer.addEventListener("load", onLoad);
    viewer.src = `/api/versions/${id1}/diff/${id2}`;
    openEditor.hidden = true;
    setStatus(`Comparing: ${v1?.name || id1} vs ${v2?.name || id2}`);
    closeSidebar();
  });
}

let loadSeq = 0;

function loadVersion(versionId) {
  activeVersionId = String(versionId);
  versionList.querySelectorAll(".tree-item").forEach((el) => el.classList.toggle("active", el.dataset.versionId === String(versionId)));

  if (baseVersionSelect) baseVersionSelect.value = "";
  if (compareVersionSelect) compareVersionSelect.value = "";

  emptyState.hidden = true;
  viewerLoading.hidden = false;
  viewer.hidden = true;

  const seq = ++loadSeq;
  let timer;

  const handler = () => {
    clearTimeout(timer);
    viewerLoading.hidden = true;
    viewer.hidden = false;
    viewer.removeEventListener("load", handler);
  };
  viewer.addEventListener("load", handler);

  viewer.addEventListener("error", function errorHandler() {
    clearTimeout(timer);
    viewerLoading.hidden = true;
    viewer.hidden = false;
    viewer.removeEventListener("error", errorHandler);
    viewer.removeEventListener("load", handler);
    setStatus("Preview failed to load.", "error");
  });

  timer = setTimeout(() => {
    if (seq === loadSeq) {
      viewerLoading.hidden = true;
      viewer.hidden = false;
      viewer.removeEventListener("load", handler);
      setStatus("Preview timed out.", "error");
    }
  }, 30000);

  viewer.src = `/api/versions/${versionId}/preview?diff=1`;
  openEditor.href = `/live-editor/?version=${versionId}`;
  openEditor.hidden = false;
  const v = allVersions.find((x) => String(x.id) === String(versionId));
  setStatus(`Comparing: ${v?.name || `Version ${versionId}`} against current curriculum`);
  closeSidebar();
}

function closeSidebar() {
  sidebar.classList.remove("open");
  sidebarOverlay.hidden = true;
}

function openSidebar() {
  sidebar.classList.add("open");
  sidebarOverlay.hidden = false;
}

if (mobileMenuBtn) mobileMenuBtn.addEventListener("click", () => sidebar.classList.contains("open") ? closeSidebar() : openSidebar());
if (sidebarOverlay) sidebarOverlay.addEventListener("click", closeSidebar);

if (toggleGroupsBtn) toggleGroupsBtn.addEventListener("click", () => {
  const workspace = document.querySelector(".workspace");
  const collapsed = workspace.classList.toggle("sidebar-collapsed");
  toggleGroupsBtn.dataset.collapsed = String(collapsed);
  if (collapsed) {
    toggleGroupsBtn.title = "Show sidebar";
  } else {
    toggleGroupsBtn.title = "Hide sidebar";
  }
});

if (showEmptyToggle) showEmptyToggle.addEventListener("change", renderFilteredVersions);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && sidebar.classList.contains("open")) closeSidebar();
});

loadVersions().catch(() => setStatus("Failed to load versions.", "error"));
