export async function api(path, { method = "GET", data } = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(path, {
      method,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", "X-Kinetic-Request": "1" },
      body: data === undefined ? undefined : JSON.stringify(data),
    });
    const payload = await response.json();
    if (!response.ok) {
      const error = new Error(
        payload.error || "The request failed. Please try again.",
      );
      error.status = response.status;
      throw error;
    }
    return payload;
  } catch (error) {
    if (error.name === "AbortError" || error instanceof TypeError) {
      throw new Error(
        "Cannot reach your workspace. Check that the local server is running, then retry.",
      );
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export function toast(message) {
  const el = document.querySelector("#toast");
  el.textContent = message;
  el.hidden = false;
  setTimeout(() => {
    el.hidden = true;
  }, 7000);
}

export function saved(message, destination = location.pathname) {
  try {
    sessionStorage.setItem("kinetic.notice", message);
  } catch {
    /* Navigation still works. */
  }
  location.assign(destination);
}

export async function submit(form, task) {
  if (form.dataset.busy === "true") return;
  const error = form.querySelector(".form-error");
  error.textContent = "";
  form.dataset.busy = "true";
  form.setAttribute("aria-busy", "true");
  const buttons = [...form.querySelectorAll("button[type=submit]")];
  buttons.forEach((button) => {
    button.disabled = true;
  });
  try {
    await task();
  } catch (reason) {
    error.textContent = reason.message || "Something went wrong. Please retry.";
  } finally {
    form.dataset.busy = "false";
    form.removeAttribute("aria-busy");
    buttons.forEach((button) => {
      button.disabled = false;
    });
  }
}

document.querySelectorAll("[data-open]").forEach((button) =>
  button.addEventListener("click", () => {
    document.getElementById(button.dataset.open).showModal();
  }),
);
document
  .querySelectorAll("[data-close]")
  .forEach((button) =>
    button.addEventListener("click", () => button.closest("dialog").close()),
  );
const theme = document.querySelector("#theme-toggle");
function updateThemeLabel() {
  theme?.setAttribute(
    "aria-label",
    `Switch to ${document.documentElement.dataset.theme === "dark" ? "light" : "dark"} theme`,
  );
}
theme?.addEventListener("click", () => {
  const value =
    document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = value;
  try {
    localStorage.setItem("kinetic.theme", value);
  } catch {
    /* Theme remains available for this page. */
  }
  updateThemeLabel();
});
updateThemeLabel();
try {
  const message = sessionStorage.getItem("kinetic.notice");
  if (message) {
    toast(message);
    sessionStorage.removeItem("kinetic.notice");
  }
} catch {
  /* Optional feedback only. */
}
const profileForm = document.querySelector("#profile-form");
const zone = document.querySelector("#profile-timezone");
if (zone?.dataset.newProfile === "true")
  zone.value = Intl.DateTimeFormat().resolvedOptions().timeZone;
profileForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  submit(profileForm, async () => {
    const fields = new FormData(profileForm);
    const result = await api("/api/profile", {
      method: "PUT",
      data: {
        name: fields.get("name"),
        weekly_goal_minutes: Number(fields.get("weekly_goal_minutes")),
        timezone: fields.get("timezone"),
      },
    });
    saved(result.message);
  });
});
