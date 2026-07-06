document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("course-form");
  const result = document.getElementById("result");
  const btn = document.getElementById("submit-btn");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    result.className = "hidden";

    const data = Object.fromEntries(new FormData(form));

    btn.disabled = true;
    btn.textContent = "Submitting...";

    try {
      const res = await fetch("/api/submissions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      const body = await res.json();

      if (!res.ok) {
        const msgs = body.detail?.map(e => e.msg) ?? [];
        result.textContent = msgs.join("\n");
        result.className = "error";
      } else {
        result.textContent = "Submission received. It will appear in Course Management after refinement completes.";
        result.className = "success";
      }
    } catch {
      result.textContent = "Network error. Check if the backend is running.";
      result.className = "error";
    } finally {
      btn.disabled = false;
      btn.textContent = "Submit Course";
    }
  });
});
