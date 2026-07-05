const params = new URLSearchParams(location.search);
const requestedSemester = params.get("sem");
const semester = document.getElementById("semester");
const viewer = document.getElementById("viewer");
const openLink = document.getElementById("open");
const downloadLink = document.getElementById("download");
const statusText = document.getElementById("status");

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

  if (!(await courseIds(sem)).length) {
    viewer.removeAttribute("src");
    openLink.removeAttribute("href");
    downloadLink.removeAttribute("href");
    statusText.textContent = sem === "all" ? "No refined courses found." : `No refined courses found for Semester ${sem}.`;
    return;
  }

  const pdf = sem === "all" ? "/api/preview/pdf" : `/api/preview/semester/${sem}/pdf`;
  viewer.src = pdf;
  openLink.href = pdf;
  downloadLink.href = `${pdf}?download=true`;
  statusText.textContent = sem === "all" ? "Overall" : `Semester ${sem}`;
}

semester.addEventListener("change", () => {
  loadSemester(semester.value);
});

(requestedSemester ? Promise.resolve(requestedSemester) : firstAvailableSemester()).then(loadSemester).catch(() => {
  statusText.textContent = "Backend unavailable.";
});
