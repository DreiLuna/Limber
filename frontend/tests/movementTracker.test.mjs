import { test } from "node:test";
import assert from "node:assert/strict";
import { MOVEMENTS, MovementTracker, readMovementPose } from "../src/vision/movementTracker.ts";

for (const id of Object.keys(MOVEMENTS)) {
  test(`${id} counts full cycles, measures holds/range, and drops interrupted cycles`, () => {
    const tracker = new MovementTracker(id);
    let now = 0, result;
    const hold = angle => { for (let i = 0; i < 6; i++) { now += 100; result = tracker.update(angle === null ? null : {angle, side:"left", points:[]}, now); } };
    const values = id === "Seated_Knee_Extension" ? [90,135,170,90] : [170,135,100,170];
    values.forEach(hold);
    assert.equal(result.reps, 1);
    const s = tracker.summary();
    assert.equal(s.reps,1); assert.equal(s.side,"left"); assert.equal(s.protocol,"movement-v1");
    assert.ok(s.hold_seconds > 0); assert.ok(s.max_angle - s.min_angle >=70);
    hold(values[1]); hold(values[2]); hold(null); hold(values[3]);
    assert.equal(result.reps,1); assert.ok(tracker.summary().tracking_ratio <1);
    tracker.reset(); assert.equal(tracker.summary(),null);
  });
}

test("hold duration excludes gaps and missing tracking", () => {
  const tracker = new MovementTracker();
  for (const t of [100,200,300,400]) tracker.update({angle:100,side:"left",points:[]},t);
  const before=tracker.summary(); assert.equal(before,null);
  tracker.update(null,1500); tracker.update(null,2500);
  assert.equal(tracker.summary().hold_seconds,.3);
  assert.ok(tracker.summary().tracking_ratio <.2);
});

test("each exercise reads its own joint chain and rejects occluded or wrong-side landmarks", () => {
  for (const [id,profile] of Object.entries(MOVEMENTS)) {
    const pose=Array.from({length:33},()=>({x:.5,y:.5,visibility:.95}));
    const [anchor,a,b,c]=profile.indices[0];
    pose[anchor]={x:.5,y:id==="Wall_Press_Up"?.7:.1,visibility:.95};
    pose[a]={x:.5,y:.3,visibility:.95}; pose[b]={x:.5,y:.5,visibility:.95};
    pose[c]={x:.5,y:.7,visibility:.95};
    assert.ok(readMovementPose(id,[pose],640,480,"left"));
    assert.equal(readMovementPose(id,[pose,pose],640,480,"left"),null);
    pose[c].visibility=.1; assert.equal(readMovementPose(id,[pose],640,480,"left"),null);
    assert.equal(readMovementPose(id,[pose],640,480,"right"),null);
  }
});
