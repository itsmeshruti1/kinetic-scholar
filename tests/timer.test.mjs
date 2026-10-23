import test from "node:test";
import assert from "node:assert/strict";
import {
  createTimer,
  advance,
  start,
  pause,
  finish,
  elapsedSeconds,
  validTimer,
} from "../static/js/timer.js";

const id = "12345678-1234-1234-1234-123456789abc";
test("deadline catches up after throttling and completes at the deadline", () => {
  const running = start(createTimer(1, 25, id), 1000);
  assert.equal(advance(running, 601000).remainingMs, 900000);
  const completed = advance(running, 2000000);
  assert.equal(completed.status, "complete");
  assert.equal(completed.completedAt, new Date(1501000).toISOString());
  assert.equal(elapsedSeconds(completed, 3000000), 1500);
});
test("pause and resume exclude paused time", () => {
  let timer = start(createTimer(1, 25, id), 0);
  timer = pause(timer, 60000);
  assert.equal(elapsedSeconds(timer, 999999), 60);
  timer = start(timer, 1000000);
  timer = pause(timer, 1060000);
  assert.equal(elapsedSeconds(timer, 2000000), 120);
});
test("early finish saves only elapsed time", () => {
  const timer = finish(start(createTimer(1, 25, id), 1000), 91000);
  assert.equal(timer.status, "complete");
  assert.equal(elapsedSeconds(timer, 1000000), 90);
  assert.equal(timer.completedAt, new Date(91000).toISOString());
});
test("serialized state restores a running timer without losing progress", () => {
  const timer = JSON.parse(JSON.stringify(start(createTimer(3, 1, id), 1000)));
  assert.ok(validTimer(timer));
  assert.equal(advance(timer, 31000).remainingMs, 30000);
  assert.equal(advance(timer, 61000).status, "complete");
});
test("invalid storage is rejected", () => {
  for (const candidate of [
    null,
    {},
    { version: 1 },
    { ...createTimer(1, 25, id), remainingMs: -1 },
    { ...createTimer(1, 25, id), status: "running", deadline: null },
  ]) {
    assert.equal(validTimer(candidate), false);
  }
});
test("starting complete timer cannot silently reset saved duration", () => {
  const timer = advance(start(createTimer(1, 1, id), 0), 60000);
  assert.deepEqual(start(timer, 90000), timer);
  assert.equal(elapsedSeconds(timer, 90000), 60);
});
