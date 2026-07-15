const semester = document.getElementById("semester");
const visibility = document.getElementById("visibility");
const search = document.getElementById("search");
const statusText = document.getElementById("status");
const table = document.getElementById("course-table");
let courses = [];
let openId = "";

function setStatus(text, kind = "") {
  statusText.textContent = text;
  statusText.className = `status-line ${kind}`.trim();
}

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text || "";
  return td;
}

function courseMatches(course) {
  const query = search.value.trim().toLowerCase();
  if (semester.value && String(course.semester) !== semester.value) return false;
  if (visibility.value === "visible" && course.visible === false) return false;
  if (visibility.value === "hidden" && course.visible !== false) return false;
  if (!query) return true;
  return `${course.course_code} ${course.course_title}`.toLowerCase().includes(query);
}

function detailsRow(course) {
  const row = document.createElement("tr");
  const td = document.createElement("td");
  td.colSpan = 6;
  const details = document.createElement("div");
  details.className = "details";
  details.append(
    line("Type", course.course_type),
    line("Tools", course.tools_languages || "Not specified"),
    line("Desirable knowledge", course.desirable_knowledge || "None"),
    line("Prelude", course.prelude || "Not specified"),
  );
  td.appendChild(details);
  row.appendChild(td);
  return row;
}

function line(label, value) {
  const div = document.createElement("div");
  const strong = document.createElement("strong");
  strong.textContent = `${label}: `;
  div.append(strong, document.createTextNode(value));
  return div;
}

function render() {
  table.replaceChildren();
  const visible = courses.filter(courseMatches);
  if (!visible.length) {
    const row = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 6;
    td.className = "empty";
    td.textContent = "No courses found.";
    row.appendChild(td);
    table.appendChild(row);
    setStatus("No courses found.");
    return;
  }

  visible.forEach((course) => {
    const row = document.createElement("tr");
    row.className = course.visible === false ? "course-row hidden-row" : "course-row";
    row.append(cell(course.semester), cell(course.course_code), cell(course.course_title), cell(course.credits));

    const visibleCell = document.createElement("td");
    visibleCell.className = "center";
    const toggle = document.createElement("input");
    toggle.type = "checkbox";
    toggle.checked = course.visible !== false;
    toggle.title = "Include in rendered documents";
    toggle.addEventListener("click", (event) => event.stopPropagation());
    toggle.addEventListener("change", () => setVisibility(course, toggle));
    visibleCell.appendChild(toggle);
    row.appendChild(visibleCell);

    const action = document.createElement("td");
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "danger";
    remove.textContent = "Delete";
    remove.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteCourse(course);
    });
    action.appendChild(remove);
    row.appendChild(action);

    row.addEventListener("click", () => {
      openId = openId === String(course.id) ? "" : String(course.id);
      render();
    });
    table.appendChild(row);
    if (openId === String(course.id)) table.appendChild(detailsRow(course));
  });
  setStatus(`${visible.length} course${visible.length === 1 ? "" : "s"}.`, "ready");
}

async function setVisibility(course, toggle) {
  const next = toggle.checked;
  setStatus("Updating visibility...");
  const response = await fetch(`/api/courses/${course.id}/visible`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ visible: next }),
  });
  if (!response.ok) {
    toggle.checked = !next;
    setStatus("Unable to update visibility.", "error");
    return;
  }
  course.visible = next;
  render();
}

async function deleteCourse(course) {
  if (!confirm(`Delete ${course.course_code || course.course_title}?`)) return;
  setStatus("Deleting course...");
  const response = await fetch(`/api/courses/${course.id}`, { method: "DELETE" });
  if (!response.ok) throw new Error("Delete failed");
  courses = courses.filter((item) => item.id !== course.id);
  if (openId === String(course.id)) openId = "";
  render();
}

async function loadCourses() {
  setStatus("Loading courses...");
  const response = await fetch("/api/courses");
  if (!response.ok) throw new Error("Unable to load courses");
  const body = await response.json();
  courses = body.courses || [];
  render();
}

semester.addEventListener("change", render);
visibility.addEventListener("change", render);
search.addEventListener("input", render);

loadCourses().catch((error) => {
  setStatus(error instanceof Error ? error.message : "Unable to load courses.", "error");
});
