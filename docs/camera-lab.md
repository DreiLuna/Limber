# Camera lab: squat-counting prototype

The signed-in navigation includes **Camera lab** at `/camera`. Select **Start
camera**, allow browser camera permission, and use a steady side view with one
person's shoulder, hip, knee and ankle in frame. Start standing. Stop if movement
is painful; this feature does not determine whether squats are appropriate for a
user, assess technique, diagnose a condition or prescribe an exercise.

## Implementation

`@mediapipe/tasks-vision` 1.2.3 runs Pose Landmarker Lite in the browser using the
CPU delegate. The SDK is loaded only on Start. The runtime downloads from
jsDelivr at that exact version; the model comes from Google's versioned
`pose_landmarker_lite/float16/1` asset. The first start needs internet access to
these hosts. No API key or backend inference service is required.

The preview starts before model loading finishes. Camera errors distinguish
denied permission, missing devices and busy devices. Use `localhost` or HTTPS;
plain HTTP at a LAN IP normally cannot access the camera. On a Mac, check the
browser's site camera permission and macOS camera privacy settings if access is
denied. Stop, navigation, a hidden tab, disconnection and model/inference errors
release the video tracks. A startup generation token prevents a late async model
or camera result from reviving a stopped session. The camera is never started on
page load.

At most about 12.5 decoded frames per second are processed synchronously; no
inference requests are queued. The same video frame is not processed twice.
The overlay shows the tracked shoulder–hip–knee–ankle chain. Each point must be
inside the image margins and have visibility of at least 0.65; a supplied
landmark presence score must also meet 0.65. Pose detection, presence and
tracking thresholds are each 0.65. Two detected people, cropped/low-confidence
limbs, tiny bodies or a horizontal torso pause counting. The visible side is
retained while valid; switching sides discards the incomplete cycle.

The knee angle is measured from hip–knee–ankle using pixel coordinates so the
image aspect ratio does not distort the calculation. Prototype thresholds are
standing at 160 degrees or above, movement at 145 or below, and bent at 110 or
below. A band must persist for 200 ms. These are engineering constants for this
demo, not clinically validated targets, and the UI does not tell a person to
reach them. A full cycle requires stable standing, a bent phase, then stable
standing, lasting at least 800 ms. A return from partial bending or a cycle that
is too fast is displayed separately. Attempts expire after 15 seconds. Missing
tracking or a gap over 400 ms discards the attempt and requires standing again.

Frames, landmarks and counts remain in memory. This feature does not record,
upload or persist them, and does not modify plans, referrals, adherence or
session logs. Model/runtime download requests disclose ordinary network request
metadata to their hosts, not camera frames. Restarting the camera resets counts.

## Verification

```bash
cd frontend
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:browser
```

The Node tests cover complete and partial cycles, starting bent, jitter,
too-fast attempts, gaps, tracking loss, side changes, timeout, reset, invalid
measurements, multiple people, cropped limbs, confidence and aspect ratio.
Playwright tests use synthetic camera streams and mocked pose outputs to cover
opt-in startup, permission-denied recovery, model-load failure, navigation
cleanup, cancellation during loading and displayed counts. They make no real
camera or inference-quality claims. CI runs both frontend test suites.

The development workspace could run the logic tests and build, but its process
sandbox prevented Chromium from launching. Browser-test results must therefore
come from CI. A real MacBook camera and actual-person trial remain required:
verify preview and overlay alignment, several complete/partial cycles,
stepping out of view, two people entering, Stop, and leaving the page. Record
observed counts and false positives/negatives; do not mark this trial complete
until someone performs it. Clothing, occlusion, perspective and model errors
can affect counts, and none of these tests establish clinical effectiveness.

Reference: [Google Pose Landmarker web guide](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker/web_js).
