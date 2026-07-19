const form = document.getElementById("course-form");
const codeInput = document.getElementById("course_code");
const previewDiv = document.getElementById("code-preview");
const creditSelect = document.getElementById("credit_category");
const submitBtn = document.getElementById("submit-btn");
const resultDiv = document.getElementById("result");

const DEPT_OFFERING = {
  CS: "CS", EC: "CS", EE: "CS", ME: "CS", BT: "CS", AI: "CS", ML: "CS",
  MA: "MA", PH: "MA", CH: "MA",
  HU: "UZ", UZ: "UZ",
};

const DEPT_TARGET = {
  CS: "CSE", EC: "ECE", EE: "EEE", ME: "ME",
  BT: "BT", AI: "AIML", ML: "AIML",
};

function parseCode(code) {
  const c = code.trim().toUpperCase().replace(/\s+/g, "");
  const m = c.match(/^UE(\d{2})([A-Z]{2})(\d{3})([A-Z\*]+)$/);
  if (!m) return null;
  const [, year, dept, numStr, suffix] = m;
  const num = parseInt(numStr, 10);
  const semesterGroup = Math.floor(num / 100);
  const creditsDigit = Math.floor(num / 10) % 10;
  const credit = [0, 2, 4, 5].includes(creditsDigit) ? String(creditsDigit) : "4";
  const isEven = suffix.startsWith("B") || suffix.endsWith("B") || suffix === "XX" || suffix === "XB";
  const semester = semesterGroup * 2 - 1 + (isEven ? 1 : 0);
  const offering = DEPT_OFFERING[dept] || "CS";
  const target = DEPT_TARGET[dept] || "CSE";
  const isLateral = suffix.includes("*");
  return { year, dept, semester, offering, target, credit, isLateral, baseCode: c };
}

function updatePreview() {
  const parsed = parseCode(codeInput.value);
  if (!parsed) {
    previewDiv.classList.add("hidden");
    previewDiv.innerHTML = "";
    return;
  }
  previewDiv.classList.remove("hidden");
  previewDiv.innerHTML = `
    <strong>Decoded:</strong>
    <span class="badge">Year: ${parsed.year}</span>
    <span class="badge">Dept: ${parsed.dept}</span>
    <span class="badge">Semester: ${parsed.semester}</span>
    <span class="badge">Offering: ${parsed.offering}</span>
    <span class="badge">Target: ${parsed.target}</span>
    <span class="badge">Credits: ${parsed.credit}</span>
    ${parsed.isLateral ? '<span class="badge lateral">Lateral Entry</span>' : ''}
  `;
  creditSelect.value = parsed.credit;
}

codeInput.addEventListener("input", updatePreview);
codeInput.addEventListener("blur", updatePreview);

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  resultDiv.classList.add("hidden");
  resultDiv.textContent = "";
  submitBtn.disabled = true;
  submitBtn.textContent = "Submitting...";

  const fd = new FormData(form);
  const data = Object.fromEntries(fd.entries());

  const parsed = parseCode(data.course_code);
  if (!parsed) {
    showError("Invalid course code format. Use format like UE25CS242B");
    submitBtn.disabled = false;
    submitBtn.textContent = "Submit Course";
    return;
  }

  data.semester = String(parsed.semester);
  data.offering_department = parsed.offering;
  data.target_department = parsed.target;
  data.credit_category = creditSelect.value || parsed.credit;

  try {
    const res = await fetch("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || "Submission failed");
    showSuccess(`Submission received! ID: ${json.submission.id}`);
    form.reset();
    previewDiv.classList.add("hidden");
  } catch (err) {
    showError(err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Submit Course";
  }
});

function showError(msg) {
  resultDiv.classList.remove("hidden", "success");
  resultDiv.classList.add("error");
  resultDiv.textContent = msg;
}

function showSuccess(msg) {
  resultDiv.classList.remove("hidden", "error");
  resultDiv.classList.add("success");
  resultDiv.textContent = msg;
}