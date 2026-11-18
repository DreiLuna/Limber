# Measured recovery feedback

Camera lab supports three versioned protocols:

| Exercise ID | Joint | Cycle | View |
| --- | --- | --- | --- |
| `Bodyweight_Squat` | Knee | Standing → bend → standing | Shoulder, hip, knee, ankle; side view |
| `Seated_Knee_Extension` | Knee | Foot down → extend → foot down | Same chain, seated side view |
| `Wall_Press_Up` | Elbow | Arms extended → bend → extended | Hip, shoulder, elbow, wrist; side view |

Start the app, sign in and open Camera lab. Choose the exercise and visible side,
then Start. Stop before adding a result. Add each exercise's result before
switching or restarting; added results remain available while collecting other
exercises. Save with the ordinary session pain and warning-symptom check.
Exercises outside the active plan are practice-only. The whole-session checkbox
starts unchecked: a camera set alone does not prove every planned exercise was
done. Choose a due scheduled session for scheduled completion; extra practice
never substitutes for it. A duplicate scheduled log returns an error and keeps
the unsaved results available.

The save transaction validates the active plan, exercise membership, summary
bounds and unique exercise IDs, snapshots the prescribed sets × reps target,
saves the session and measurements together, and runs reevaluation. Referral
rules still win over all camera evidence. Invalid input leaves no partial log.
Only authenticated users can read their own results at `/api/measurements`.
Saved results remain visible on Progress after a plan is retired.

## What is measured

MediaPipe Pose Landmarker Lite 1.2.3 runs client-side using the CPU delegate,
loaded only on Start. Runtime assets come from versioned jsDelivr URLs and the
model from Google's versioned Lite asset. No API key is needed. Camera access
requires localhost or HTTPS. The preview starts before the model loads. Stop,
navigation, hidden tabs and camera/model errors release resources, including
late asynchronous initialization. Recording stops at 30 minutes.

Inference is throttled to roughly 12.5 decoded frames per second. Exactly one
person and all required points on the selected side must be visible with
confidence at least 0.65. Gaps over 400ms discard an incomplete cycle. A band
must persist for 200ms; full cycles take at least 800ms and expire after 15s.
Each protocol supplies its own joint chain and angle bands. Seated extension
reverses the counting direction; the displayed angle remains the original one.
Repetitions, partial attempts, time in the bent/extended band, observed minimum
and maximum 2D angles, duration and time-based tracking coverage are summarized.
Hold time excludes lost tracking and gaps. It is an observation, not a
prescribed hold duration or proof of correct posture. The angle span is not a
clinical range-of-motion measurement.

Video, photos and landmark coordinates never leave the browser. Saving sends
numeric summaries and the user's pain responses to the authenticated API; the
UI explains this before Save. Restart and Reset clear the current recording.
Nothing is uploaded automatically. Model requests expose ordinary network
request metadata to the asset hosts.

## How measurements affect a plan

The existing priority order remains referral, reduce, increase, reassess,
continue. An increase now also requires the last two full plan weeks to have:
low pain (maximum 3/10, including extra logs), at least 80% scheduled completion
with all supported camera exercises measured, prescribed repetition targets met,
at least 80% tracking, no more than 25% partial attempts, at least five seconds
per recording and at least ten degrees of observed angle span. Per-exercise
median span may not decline more than ten degrees, and the same side must be
used. Missing measurements block an increase but do not block referral,
reduction or reassessment. Plans with no supported camera exercise cannot
increase automatically. These policies are centralized in `thresholds.yaml`.

Weekly decisions remain idempotent: adding evidence after a decision in the
same plan week does not apply another adjustment. New urgent symptoms still
trigger referral immediately. The camera is additional evidence, never proof
that an exercise is medically suitable. Charts and the data table separate
exercise and side and show saved counts against the server-snapshotted target,
hold time, angle span and tracking coverage.

## Verification

```bash
cd backend
alembic upgrade head
python scripts/import_catalog.py --load-only
pytest
cd ../frontend
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:browser
```

Logic tests cover all three protocols, holds, confidence, missing tracking,
partial cycles, angle geometry and timing. API tests cover persistence, user
isolation, invalid/duplicate/unplanned input, referral priority and measured
progression gates. Browser tests cover camera lifecycle and synthetic
three-exercise counts plus save → Progress rendering. Synthetic inputs test
software behavior, not actual-person detection accuracy. For a repeatable live
demo, compare observed counts and overlay alignment for each exercise, record
partial attempts and tracking loss, then reload Progress to check persistence.

See [guidance review](guideline-review.md) for sources and changes, and
[hosting](hosting.md) for the full-stack deployment setup.
