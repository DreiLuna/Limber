import assert from "node:assert/strict";
import { test } from "node:test";
import { jointAngle, readPose, SquatCounter } from "../src/vision/squatCounter.ts";

const sample = (angle, side = "left") => ({ angle, side, points: [] });
function session() {
  const counter = new SquatCounter();
  let now = 100;
  let result;
  return {
    counter,
    hold(angle, frames = 4, side = "left") {
      for (let i = 0; i < frames; i++) {
        result = counter.update(angle === null ? null : sample(angle, side), now);
        now += 100;
      }
      return result;
    },
    gap(ms) { now += ms; },
  };
}

test("counts a stable standing, bent, standing cycle once", () => {
  const s = session();
  s.hold(170); s.hold(135); s.hold(100);
  assert.equal(s.hold(170).reps, 1);
  assert.equal(s.hold(170, 20).reps, 1);
  s.hold(135); s.hold(100);
  assert.equal(s.hold(170).reps, 2);
});

test("starting bent does not count until a new full cycle", () => {
  const s = session();
  s.hold(100);
  assert.equal(s.hold(170).reps, 0);
  s.hold(135); s.hold(100);
  assert.equal(s.hold(170).reps, 1);
});

test("partial movement is shown separately and does not count as a rep", () => {
  const s = session();
  s.hold(170); s.hold(135);
  const result = s.hold(170);
  assert.equal(result.reps, 0);
  assert.equal(result.partials, 1);
});

test("brief angle spikes and standing jitter do not count", () => {
  const s = session();
  s.hold(170); s.hold(100, 1); s.hold(165, 1); s.hold(155, 1);
  assert.equal(s.hold(170).reps, 0);
});

test("a too-fast full-looking movement does not count", () => {
  const s = session();
  s.hold(170); s.hold(100, 3);
  const result = s.hold(170, 3);
  assert.equal(result.reps, 0);
  assert.equal(result.partials, 1);
});

test("tracking loss discards an incomplete cycle but preserves completed counts", () => {
  const s = session();
  s.hold(170); s.hold(135); s.hold(100); s.hold(170);
  s.hold(135); s.hold(100); s.hold(null);
  assert.equal(s.hold(170).reps, 1);
  s.hold(135); s.hold(100);
  assert.equal(s.hold(170).reps, 2);
});

test("a stalled frame or changed tracked side discards the attempt", () => {
  for (const interrupt of ["gap", "side"]) {
    const s = session();
    s.hold(170); s.hold(135); s.hold(100);
    if (interrupt === "gap") s.gap(800);
    assert.equal(s.hold(170, 4, interrupt === "side" ? "right" : "left").reps, 0);
  }
});

test("an expired attempt cannot count", () => {
  const s = session();
  s.hold(170); s.hold(135); s.hold(100, 155);
  assert.equal(s.hold(170).reps, 0);
});

test("reset clears counts and requires standing again", () => {
  const s = session();
  s.hold(170); s.hold(135); s.hold(100); s.hold(170);
  assert.equal(s.counter.reset().reps, 0);
  s.hold(100);
  assert.equal(s.hold(170).reps, 0);
});

test("invalid or out-of-order measurements reset tracking", () => {
  const counter = new SquatCounter();
  for (const angle of [NaN, Infinity, -1, 181]) {
    assert.equal(counter.update(sample(angle), performance.now()).phase, "waiting");
  }
  counter.update(sample(170), 10_000);
  assert.equal(counter.update(sample(100), 9000).phase, "waiting");
});

function pose() {
  const points = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.5, visibility: 0.9, presence: 0.9 }));
  for (const [shoulder, hip, knee, ankle] of [[11, 23, 25, 27], [12, 24, 26, 28]]) {
    points[shoulder].y = 0.2; points[hip].y = 0.4; points[knee].y = 0.6; points[ankle].y = 0.8;
  }
  return points;
}

test("reads a single visible body and retains the preferred side", () => {
  const p = pose();
  assert.equal(readPose([p], 640, 480).angle, 180);
  assert.equal(readPose([p], 640, 480, "right").side, "right");
  p.forEach((point) => { delete point.presence; });
  assert.equal(readPose([p], 640, 480).angle, 180);
});

test("rejects no person, multiple people, low confidence and cropped limbs", () => {
  assert.equal(readPose([], 640, 480), null);
  assert.equal(readPose([pose(), pose()], 640, 480), null);
  for (const change of [
    (p) => { p[27].visibility = 0.2; p[28].visibility = 0.2; },
    (p) => { p[23].presence = 0.2; p[24].presence = 0.2; },
    (p) => { p[27].y = 1.1; p[28].y = 1.1; },
    (p) => { p[23].x = NaN; p[24].x = NaN; },
    (p) => { p[11].y = 0.4; p[12].y = 0.4; },
  ]) {
    const p = pose(); change(p);
    assert.equal(readPose([p], 640, 480), null);
  }
});

test("angles use image aspect ratio and reject degenerate joints", () => {
  const p = { x: 0.5, y: 0.5 };
  const angle = jointAngle({ x: 0.25, y: 0.25 }, p, { x: 0.75, y: 0.25 }, 640, 480);
  assert.ok(Math.abs(angle - 106.2602) < 0.01);
  assert.equal(jointAngle(p, p, p, 640, 480), null);
});
