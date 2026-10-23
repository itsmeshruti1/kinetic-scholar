import { api, submit, saved } from "./common.js";
const form = document.querySelector("#plan-form");
form?.addEventListener("submit", (event) => {
  event.preventDefault();
  submit(form, async () => {
    const fields = new FormData(form);
    await api("/api/plan", {
      method: "POST",
      data: {
        total_minutes: Number(fields.get("total_minutes")),
        mode: fields.get("mode"),
      },
    });
    saved("Your study plan is ready. Breaks are included in the time budget.");
  });
});
