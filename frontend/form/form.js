const form = document.getElementById("course-form");
const codeInput = document.getElementById("course_code");
const previewDiv = document.getElementById("code-preview");
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
  const baseSem = Math.floor(num / 100);
  const isEven = suffix.startsWith("B") || suffix.endsWith("B") || suffix === "XX" || suffix === "XB";
  const semester = baseSem + (isEven ? 1 : 0);
  const offering = DEPT_OFFERING[dept] || "CS";
  const target = DEPT_TARGET[dept] || "CSE";
  let credit = "4";
  if (suffix === "A*" || suffix === "B*") credit = "0";
  else if (suffix.endsWith("XX") || suffix.endsWith("AX") || suffix.endsWith("BX") || ["AXX","ABX","BAX","BBX"].includes(suffix)) credit = "5";
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

  // Validate course code
  const parsed = parseCode(data.course_code);
  if (!parsed) {
    showError("Invalid course code format. Use format like UE25CS242B");
    submitBtn.disabled = false;
    submitBtn.textContent = "Submit Course";
    return;
  }

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