const params = new URLSearchParams(location.search);
const requestedSemester = params.get("sem");
const storedYear = localStorage.getItem("curriculumYear") || "";
const requestedYear = params.get("curriculum_year") || params.get("year") || storedYear;
const semester = document.getElementById("semester");
const course = document.getElementById("course");
const curriculumYear = document.getElementById("curriculum-year");
const viewer = document.getElementById("viewer");
const openLink = document.getElementById("open");
const downloadLink = document.getElementById("download");
const statusText = document.getElementById("status");
const loading = document.getElementById("loading");
curriculumYear.value = requestedYear;
if (requestedYear) localStorage.setItem("curriculumYear", requestedYear);

function clearPreview(message) {
  viewer.removeAttribute("src");
  openLink.removeAttribute("href");
  downloadLink.removeAttribute("href");
  statusText.textContent = message;
  if (loading) loading.hidden = true;
}

function yearValue() {
  return curriculumYear.value.trim();
}

function saveYear() {
  if (yearValue()) localStorage.setItem("curriculumYear", yearValue());
}

function pdfUrl(sem, download = false) {
  const path = sem === "all" ? "/api/preview/pdf" : `/api/preview/semester/${sem}/pdf`;
  const query = new URLSearchParams({ curriculum_year: yearValue() });
  if (download) query.set("download", "true");
  return `${path}?${query}`;
}

function coursePdfUrl(refinedId, download = false) {
  const query = new URLSearchParams({ curriculum_year: yearValue() });
  if (download) query.set("download", "true");
  return `/api/preview/course/${refinedId}/pdf?${query}`;
}

async function courseIds(sem) {
  const url = sem === "all" ? "/api/preview/courses" : `/api/preview/semester/${sem}/courses`;
  const response = await fetch(url);
  if (!response.ok) return [];
  const body = await response.json();
  return body.course_ids || [];
}

async function fetchCourses(sem) {
  if (sem === "all") return [];
  const url = `/api/preview/semester/${sem}/courses`;
  const response = await fetch(url);
  if (!response.ok) return [];
  const body = await response.json();
  return body.courses || [];
}

async function firstAvailableSemester() {
  if ((await courseIds("all")).length) return "all";
  for (let sem = 1; sem <= 8; sem += 1) {
    if ((await courseIds(sem)).length) return String(sem);
  }
  return "all";
}

function loadIntoViewer(url, label) {
  if (loading) loading.hidden = false;
  viewer.hidden = true;

  const onLoad = () => {
    if (loading) loading.hidden = true;
    viewer.hidden = false;
    viewer.removeEventListener("load", onLoad);
  };
  viewer.addEventListener("load", onLoad);

  viewer.src = url;
  openLink.href = url;
  openLink.target = "_blank";
  downloadLink.href = url.includes("?") ? url + "&download=true" : url + "?download=true";
  statusText.textContent = label;
}

async function loadSemester(sem) {
  semester.value = sem;
  statusText.textContent = "Loading...";

  if (!/^\d{4}-\d{4}$/.test(yearValue())) {
    clearPreview("Set academic year on the dashboard to preview.");
    course.hidden = true;
    return;
  }

  if (!(await courseIds(sem)).length) {
    clearPreview(sem === "all" ? "No refined courses found." : `No refined courses found for Semester ${sem}.`);
    course.hidden = true;
    return;
  }

  if (sem === "all") {
    course.hidden = true;
    course.innerHTML = "";
    loadIntoViewer(pdfUrl(sem), "Overall");
    return;
  }

  const courses = await fetchCourses(sem);
  course.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = `All Semester ${sem} courses`;
  course.appendChild(placeholder);
  for (const c of courses) {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `${c.course_code} - ${c.course_title}`;
    course.appendChild(opt);
  }
  course.value = "";
  course.hidden = false;

  loadIntoViewer(pdfUrl(sem), `Semester ${sem}`);
}

function loadSelectedCourse() {
  const selectedId = course.value;
  if (!selectedId) {
    loadIntoViewer(pdfUrl(semester.value), `Semester ${semester.value}`);
    return;
  }
  const opt = course.options[course.selectedIndex];
  loadIntoViewer(coursePdfUrl(selectedId), opt.textContent);
}

semester.addEventListener("change", () => {
  loadSemester(semester.value);
});

course.addEventListener("change", loadSelectedCourse);

curriculumYear.addEventListener("change", () => {
  saveYear();
  loadSemester(semester.value);
});

(requestedSemester ? Promise.resolve(requestedSemester) : firstAvailableSemester()).then(loadSemester).catch(() => {
  statusText.textContent = "Backend unavailable.";
});
