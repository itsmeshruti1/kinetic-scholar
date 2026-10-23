import { api, submit, saved } from "./common.js";
import {
  createTimer,
  advance,
  start,
  pause,
  finish,
  elapsedSeconds,
  validTimer,
} from "./timer.js";

const KEY = "kinetic.timer.v2";
const subject = document.querySelector("#timer-subject");
const minutes = document.querySelector("#timer-minutes");
const toggle = document.querySelector("#timer-toggle");
const finishButton = document.querySelector("#timer-finish");
const resetButton = document.querySelector("#timer-reset");
const errorEl = document.querySelector("#timer-error");
const dialog = document.querySelector("#completion-dialog");
const form = document.querySelector("#completion-form");
let timer,
  ownsTimer = false,
  storageAvailable = true;

document
  .querySelector("#distraction-toggle")
  ?.addEventListener("click", (event) => {
    const on = document.body.classList.toggle("distraction-free");
    event.currentTarget.setAttribute("aria-pressed", String(on));
    event.currentTarget.textContent = on
      ? "Exit distraction-free mode"
      : "Distraction-free mode";
  });

function store() {
  try {
    localStorage.setItem(KEY, JSON.stringify(timer));
  } catch {
    storageAvailable = false;
    errorEl.textContent =
      "Browser storage is unavailable. Keep this page open until you save your session.";
  }
}

function configure() {
  if (!minutes.checkValidity()) {
    minutes.reportValidity();
    return false;
  }
  timer = createTimer(
    Number(subject.value),
    Number(minutes.value),
    crypto.randomUUID(),
  );
  store();
  render();
  return true;
}

function render() {
  if (!timer) return;
  const before = timer.status;
  timer = advance(timer, Date.now());
  if (before !== timer.status) {
    store();
    if (timer.status === "complete" && !dialog.open) openFeedback();
  }
  const seconds = Math.ceil(timer.remainingMs / 1000);
  document.querySelector("#timer-display").textContent =
    `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  document.title = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")} · Focus · Kinetic Scholar`;
  document.querySelector("#timer-progress").value =
    ((timer.totalMs - timer.remainingMs) / timer.totalMs) * 100;
  const labels = {
    idle: "READY WHEN YOU ARE",
    running: "ONE THING AT A TIME",
    paused: "TAKE A BREATH",
    complete: "SESSION READY TO SAVE",
  };
  document.querySelector("#timer-status").textContent = labels[timer.status];
  toggle.textContent =
    timer.status === "running"
      ? "Pause"
      : timer.status === "paused"
        ? "Resume focus ↗"
        : "Start focus ↗";
  toggle.disabled = !ownsTimer || timer.status === "complete";
  finishButton.disabled = !ownsTimer || elapsedSeconds(timer, Date.now()) < 60;
  finishButton.textContent =
    timer.status === "complete" ? "Save session ↗" : "Finish & save";
  resetButton.disabled = !ownsTimer || timer.status === "idle";
  subject.disabled = minutes.disabled = !ownsTimer || timer.status !== "idle";
  document.querySelector("#timer-note").textContent =
    timer.status === "complete"
      ? "Good work. Save your session, then take a five-minute break."
      : timer.status === "paused"
        ? "The clock is paused. Your progress is safe."
        : "One session. One small step forward.";
}

function openFeedback() {
  document.querySelector("#completion-summary").textContent =
    `${Math.floor(elapsedSeconds(timer, Date.now()) / 60)} minutes of focused work. How did it feel?`;
  if (timer.submission) {
    form.elements.focus_rating.value = timer.submission.focus_rating;
    form.elements.difficulty.value = timer.submission.difficulty;
  }
  form.querySelectorAll("select").forEach((el) => {
    el.disabled = Boolean(timer.submission);
  });
  if (!dialog.open) dialog.showModal();
}

async function initialize() {
  ownsTimer = true;
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const candidate = JSON.parse(raw);
      if (validTimer(candidate)) timer = candidate;
      else
        errorEl.textContent =
          "An invalid timer draft was ignored. Saved sessions are unaffected.";
    }
  } catch {
    errorEl.textContent =
      "A previous timer could not be restored. Saved sessions are unaffected.";
  }
  if (timer && timer.status !== "idle") {
    const available = [...subject.options].some(
      (option) => Number(option.value) === timer.subjectId,
    );
    if (!available) {
      ownsTimer = false;
      errorEl.textContent =
        "Your pending timer belongs to an archived subject. Restore it on Subjects, then reload this page. The draft is preserved.";
      render();
      return;
    }
    subject.value = timer.subjectId;
    minutes.value = timer.totalMs / 60000;
    render();
  } else {
    const params = new URLSearchParams(location.search);
    if (
      [...subject.options].some(
        (option) => option.value === params.get("subject"),
      )
    )
      subject.value = params.get("subject");
    const plannedMinutes = Number(params.get("minutes"));
    if (
      Number.isInteger(plannedMinutes) &&
      plannedMinutes >= 1 &&
      plannedMinutes <= 240
    )
      minutes.value = plannedMinutes;
    configure();
  }
  if (timer.status === "complete" && !dialog.open) openFeedback();
  setInterval(render, 250);
  document.addEventListener("visibilitychange", render);
}

if (subject) {
  toggle.disabled =
    finishButton.disabled =
    resetButton.disabled =
    subject.disabled =
    minutes.disabled =
      true;
  if (navigator.locks) {
    navigator.locks.request(
      "kinetic-focus-timer",
      { ifAvailable: true },
      async (lock) => {
        if (!lock) {
          errorEl.textContent =
            "A Focus tab is already open. Close it, then reload this page to continue the same timer.";
          return;
        }
        await initialize();
        // Keep one tab in charge until navigation releases this document's lock.
        await new Promise(() => {});
      },
    );
  } else {
    errorEl.textContent =
      "This browser cannot coordinate timer tabs. Use a current browser on localhost.";
  }
  subject.addEventListener("change", configure);
  minutes.addEventListener("change", configure);
  toggle.addEventListener("click", () => {
    if (!ownsTimer) return;
    if (timer.status === "idle" && !configure()) return;
    timer =
      timer.status === "running"
        ? pause(timer, Date.now())
        : start(timer, Date.now());
    store();
    render();
  });
  finishButton.addEventListener("click", () => {
    if (!ownsTimer || elapsedSeconds(timer, Date.now()) < 60) return;
    timer = finish(timer, Date.now());
    store();
    render();
    openFeedback();
  });
  resetButton.addEventListener("click", () => {
    if (
      !ownsTimer ||
      !confirm(
        "Discard this unsaved timer? Your saved study history will stay unchanged.",
      )
    )
      return;
    if (dialog.open) dialog.close();
    configure();
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submit(form, async () => {
      if (!timer.submission) {
        timer.submission = {
          id: timer.id,
          subject_id: timer.subjectId,
          duration_seconds: elapsedSeconds(timer, Date.now()),
          completed_at: timer.completedAt,
          focus_rating: Number(form.elements.focus_rating.value),
          difficulty: form.elements.difficulty.value,
        };
        store();
      }
      form.querySelectorAll("select").forEach((el) => {
        el.disabled = true;
      });
      await api("/api/sessions", { method: "POST", data: timer.submission });
      try {
        localStorage.removeItem(KEY);
      } catch {
        /* Server-side IDs prevent duplicate retries. */
      }
      saved("Session saved. Take a breath — you earned it.", "/data");
    });
  });
  window.addEventListener("beforeunload", (event) => {
    if (!storageAvailable && timer && timer.status !== "idle") {
      event.preventDefault();
      event.returnValue = "";
    }
  });
}
