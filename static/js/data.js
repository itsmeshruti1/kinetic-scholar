import { api, submit, saved, toast } from "./common.js";
const bars = [...document.querySelectorAll("[data-seconds]")];
const max = Math.max(1, ...bars.map((bar) => Number(bar.dataset.seconds)));
bars.forEach((bar) => {
  bar.style.height = `${(Number(bar.dataset.seconds) / max) * 100}%`;
});
const form = document.querySelector("#distribution-form");
if (form) {
  const inputs = [...form.querySelectorAll("[data-subject-id]")];
  const totalEl = document.querySelector("#allocation-total");
  function total() {
    const value = inputs.reduce((sum, input) => sum + Number(input.value), 0);
    totalEl.textContent = `Total: ${value}%${value === 100 ? "" : " · must equal 100%"}`;
    totalEl.classList.toggle("invalid", value !== 100);
    return value;
  }
  inputs.forEach((input) => input.addEventListener("input", total));
  total();
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submit(form, async () => {
      if (total() !== 100)
        throw new Error("Target percentages must add up to exactly 100%.");
      const result = await api("/api/distribution", {
        method: "PUT",
        data: {
          distribution: inputs.map((input) => ({
            subject_id: Number(input.dataset.subjectId),
            percent: Number(input.value),
          })),
        },
      });
      saved(result.message);
    });
  });
  document
    .querySelector("#suggest-distribution")
    .addEventListener("click", async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        const data = await api("/api/distribution/suggestion");
        data.distribution.forEach((item) => {
          const input = inputs.find(
            (el) => Number(el.dataset.subjectId) === item.subject_id,
          );
          if (input) input.value = item.percent;
        });
        total();
        toast("Suggestion applied. Review the values, then save your targets.");
      } catch (error) {
        form.querySelector(".form-error").textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
}
