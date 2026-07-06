const params = new URLSearchParams(location.search);
const requestedSemester = params.get("sem");
const storedYear = localStorage.getItem("curriculumYear") || "";
const requestedYear = params.get("curriculum_year") || params.get("year") || storedYear;
const semester = document.getElementById("semester");
const curriculumYear = document.getElementById("curriculum-year");
const viewer = document.getElementById("viewer");
const openLink = document.getElementById("open");
const downloadLink = document.getElementById("download");
const statusText = document.getElementById("status");
curriculumYear.value = requestedYear;
if (requestedYear) localStorage.setItem("curriculumYear", requestedYear);

function clearPreview(message) {
  viewer.removeAttribute("src");
  openLink.removeAttribute("href");
  downloadLink.removeAttribute("href");
  statusText.textContent = message;
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

async function courseIds(sem) {
  const url = sem === "all" ? "/api/preview/courses" : `/api/preview/semester/${sem}/courses`;
  const response = await fetch(url);
  if (!response.ok) return [];
  const body = await response.json();
  return body.course_ids || [];
}

async function firstAvailableSemester() {
  if ((await courseIds("all")).length) return "all";
  for (let sem = 1; sem <= 8; sem += 1) {
    if ((await courseIds(sem)).length) return String(sem);
  }
  return "all";
}

async function loadSemester(sem) {
  semester.value = sem;
  statusText.textContent = "Loading...";

  if (!/^\d{4}-\d{4}$/.test(yearValue())) {
    clearPreview("Enter academic year as YYYY-YYYY.");
    return;
  }

  if (!(await courseIds(sem)).length) {
    clearPreview(sem === "all" ? "No refined courses found." : `No refined courses found for Semester ${sem}.`);
    return;
  }

  const pdf = pdfUrl(sem);
  viewer.src = pdf;
  openLink.href = pdf;
  downloadLink.href = pdfUrl(sem, true);
  statusText.textContent = sem === "all" ? "Overall" : `Semester ${sem}`;
}

semester.addEventListener("change", () => {
  loadSemester(semester.value);
});

curriculumYear.addEventListener("change", () => {
  saveYear();
  loadSemester(semester.value);
});

(requestedSemester ? Promise.resolve(requestedSemester) : firstAvailableSemester()).then(loadSemester).catch(() => {
  statusText.textContent = "Backend unavailable.";
});
