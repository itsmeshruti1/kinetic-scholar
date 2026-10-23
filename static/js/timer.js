// Pure timer transitions. A deadline avoids losing time when a browser throttles ticks.
export function createTimer(subjectId, minutes, id) {
  return {
    version: 1,
    id,
    subjectId,
    totalMs: minutes * 60000,
    remainingMs: minutes * 60000,
    deadline: null,
    status: "idle",
    completedAt: null,
  };
}

export function advance(timer, now) {
  if (timer.status !== "running") return { ...timer };
  const remainingMs = Math.max(
    0,
    Math.min(timer.totalMs, timer.deadline - now),
  );
  return {
    ...timer,
    remainingMs,
    status: remainingMs ? "running" : "complete",
    completedAt: remainingMs ? null : new Date(timer.deadline).toISOString(),
  };
}

export function start(timer, now) {
  if (!["idle", "paused"].includes(timer.status)) return { ...timer };
  return { ...timer, deadline: now + timer.remainingMs, status: "running" };
}

export function pause(timer, now) {
  const current = advance(timer, now);
  return current.status === "complete"
    ? current
    : { ...current, status: "paused", deadline: null };
}

export function finish(timer, now) {
  const current = advance(timer, now);
  return {
    ...current,
    status: "complete",
    deadline: null,
    completedAt: current.completedAt || new Date(now).toISOString(),
  };
}

export function elapsedSeconds(timer, now) {
  const current = advance(timer, now);
  return Math.floor((current.totalMs - current.remainingMs) / 1000);
}

export function validTimer(timer) {
  return Boolean(
    timer &&
    timer.version === 1 &&
    typeof timer.id === "string" &&
    /^[0-9a-f-]{36}$/i.test(timer.id) &&
    Number.isInteger(timer.subjectId) &&
    timer.subjectId > 0 &&
    Number.isFinite(timer.totalMs) &&
    timer.totalMs >= 60000 &&
    timer.totalMs <= 14400000 &&
    Number.isFinite(timer.remainingMs) &&
    timer.remainingMs >= 0 &&
    timer.remainingMs <= timer.totalMs &&
    ["idle", "running", "paused", "complete"].includes(timer.status) &&
    (timer.status !== "running" || Number.isFinite(timer.deadline)) &&
    (timer.status !== "complete" ||
      Number.isFinite(Date.parse(timer.completedAt))),
  );
}
