import { api, submit, saved } from "./common.js";
const dialog = document.querySelector("#subject-dialog");
const form = document.querySelector("#subject-form");
function openEditor(button) {
  form.reset();
  form.querySelector(".form-error").textContent = "";
  const editing = Boolean(button?.dataset.editSubject);
  form.elements.id.value = editing ? button.dataset.editSubject : "";
  form.elements.name.value = editing ? button.dataset.name : "";
  form.elements.importance.value = editing ? button.dataset.importance : "5";
  form.elements.archived.checked = editing && button.dataset.archived === "1";
  document.querySelector("#archive-label").hidden = !editing;
  document.querySelector("#subject-title").textContent = editing
    ? "Edit your subject"
    : "Add a subject";
  dialog.showModal();
}
document
  .querySelector("#add-subject")
  .addEventListener("click", () => openEditor());
document
  .querySelector("[data-trigger-add]")
  ?.addEventListener("click", () => openEditor());
document
  .querySelectorAll("[data-edit-subject]")
  .forEach((button) =>
    button.addEventListener("click", () => openEditor(button)),
  );
form.addEventListener("submit", (event) => {
  event.preventDefault();
  submit(form, async () => {
    const id = form.elements.id.value;
    const data = {
      name: form.elements.name.value,
      importance: Number(form.elements.importance.value),
    };
    if (id) data.archived = form.elements.archived.checked;
    const result = await api(id ? `/api/subjects/${id}` : "/api/subjects", {
      method: id ? "PATCH" : "POST",
      data,
    });
    saved(result.message);
  });
});
document.querySelector("#subject-search").addEventListener("input", (event) => {
  const query = event.target.value.trim().toLowerCase();
  const cards = [...document.querySelectorAll("[data-search]")];
  cards.forEach((card) => {
    card.hidden = !card.dataset.search.includes(query);
  });
  document.querySelector("#search-empty").hidden =
    !cards.length || cards.some((card) => !card.hidden);
});
