import { api, submit, saved, toast } from "./common.js";
const form = document.querySelector("#manual-form");
const KEY = "kinetic.manual-draft";
let pending;
try {
  pending = JSON.parse(sessionStorage.getItem(KEY) || "null");
} catch {
  /* A malformed draft never changes saved history. */
}
if (pending && form) {
  form.elements.subject_id.value = pending.subject_id;
  form.elements.minutes.value = pending.duration_seconds / 60;
  form.elements.focus_rating.value = pending.focus_rating;
  form.elements.difficulty.value = pending.difficulty;
  form.querySelectorAll("input,select").forEach((input) => {
    input.disabled = true;
  });
  toast(
    "An unsent manual session is preserved. Open Log a session to retry saving it.",
  );
}
form?.addEventListener("submit", (event) => {
  event.preventDefault();
  submit(form, async () => {
    if (!pending) {
      const fields = new FormData(form);
      pending = {
        id: crypto.randomUUID(),
        subject_id: Number(fields.get("subject_id")),
        duration_seconds: Number(fields.get("minutes")) * 60,
        focus_rating: Number(fields.get("focus_rating")),
        difficulty: fields.get("difficulty"),
        completed_at: new Date().toISOString(),
      };
      try {
        sessionStorage.setItem(KEY, JSON.stringify(pending));
      } catch {
        /* Retry remains available in this tab. */
      }
    }
    // Freeze an uncertain submission so retrying cannot create another session.
    form.querySelectorAll("input,select").forEach((input) => {
      input.disabled = true;
    });
    try {
      await api("/api/sessions", { method: "POST", data: pending });
    } catch (error) {
      if (error.status === 400) {
        pending = null;
        try {
          sessionStorage.removeItem(KEY);
        } catch {
          /* Optional draft persistence. */
        }
        form.querySelectorAll("input,select").forEach((input) => {
          input.disabled = false;
        });
      }
      throw error;
    }
    try {
      sessionStorage.removeItem(KEY);
    } catch {
      /* A retry remains idempotent. */
    }
    saved("Session saved. Your progress is up to date.", "/data");
  });
});
