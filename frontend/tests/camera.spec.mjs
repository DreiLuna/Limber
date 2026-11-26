import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/notifications", (route) => route.fulfill({ json: [] }));
  await page.route("**/@mediapipe_tasks-vision.js*", (route) => route.fulfill({
    contentType: "application/javascript",
    body: `
      export const FilesetResolver = { forVisionTasks: async () => ({}) };
      export const PoseLandmarker = {
        createFromOptions: async () => {
          if (window.cameraTest.modelFails) throw new Error('offline');
          if (window.cameraTest.delayModel) await new Promise(r => window.cameraTest.resolveModel = r);
          return {
            detectForVideo: () => ({ landmarks: window.cameraTest.poses }),
            close: () => { window.cameraTest.closed++; },
          };
        }
      };
    `,
  }));
  await page.addInitScript(() => {
    localStorage.setItem("limber_token", "local-browser-test");
    window.cameraTest = { poses: [], starts: 0, stops: 0, closed: 0, denied: false, modelFails: false, delayModel: false };
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", { value: async () => {
      window.cameraTest.starts++;
      if (window.cameraTest.denied) throw new DOMException("Denied", "NotAllowedError");
      const canvas = document.createElement("canvas");
      canvas.width = 640; canvas.height = 480;
      const ctx = canvas.getContext("2d");
      const timer = setInterval(() => { ctx.fillStyle = "#132d38"; ctx.fillRect(0, 0, 640, 480); }, 50);
      const stream = canvas.captureStream(20);
      const track = stream.getVideoTracks()[0];
      window.cameraTest.track = track;
      const original = track.stop.bind(track);
      track.stop = () => { window.cameraTest.stops++; clearInterval(timer); original(); };
      return stream;
    } });
  });
  await page.goto("/camera");
});

test("camera is opt-in and stop releases the camera and model", async ({ page }) => {
  await expect(page.getByRole("heading", { name: "See your movement, count each cycle" })).toBeVisible();
  expect(await page.evaluate(() => window.cameraTest.starts)).toBe(0);
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await expect(page.getByText("Camera on · processed locally", { exact: true })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("Tracking paused");
  await page.getByRole("button", { name: "Stop camera", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Camera is off.");
  expect(await page.evaluate(() => window.cameraTest.stops)).toBe(1);
  expect(await page.evaluate(() => window.cameraTest.closed)).toBe(1);
});

test("permission denial gives recovery instructions and allows retry", async ({ page }) => {
  await page.evaluate(() => { window.cameraTest.denied = true; });
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Camera access was denied");
  await expect(page.getByRole("button", { name: "Start camera", exact: true })).toBeEnabled();
  await page.evaluate(() => { window.cameraTest.denied = false; });
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await expect(page.getByText("Camera on · processed locally", { exact: true })).toBeVisible();
});

test("model failure stops the opened camera", async ({ page }) => {
  await page.evaluate(() => { window.cameraTest.modelFails = true; });
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("pose model could not load");
  expect(await page.evaluate(() => window.cameraTest.stops)).toBe(1);
});

test("navigation closes the camera", async ({ page }) => {
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await expect(page.getByText("Camera on · processed locally", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Library", exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.cameraTest.stops)).toBe(1);
  expect(await page.evaluate(() => window.cameraTest.closed)).toBe(1);
});

test("stop during model loading cannot restart the camera later", async ({ page }) => {
  await page.evaluate(() => { window.cameraTest.delayModel = true; });
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await expect.poll(() => page.evaluate(() => typeof window.cameraTest.resolveModel)).toBe("function");
  await page.getByRole("button", { name: "Stop camera", exact: true }).click();
  await page.evaluate(() => window.cameraTest.resolveModel());
  await expect.poll(() => page.evaluate(() => window.cameraTest.closed)).toBe(1);
  await expect(page.getByRole("status")).toHaveText("Camera is off.");
  expect(await page.evaluate(() => window.cameraTest.stops)).toBe(1);
});

test("disconnect during model loading releases the camera and allows retry", async ({ page }) => {
  await page.evaluate(() => { window.cameraTest.delayModel = true; });
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await expect.poll(() => page.evaluate(() => typeof window.cameraTest.resolveModel)).toBe("function");
  await page.evaluate(() => window.cameraTest.track.dispatchEvent(new Event("ended")));
  await expect(page.getByRole("alert")).toContainText("The camera disconnected.");
  await page.evaluate(() => {
    window.cameraTest.delayModel = false;
    window.cameraTest.resolveModel();
  });
  await expect.poll(() => page.evaluate(() => window.cameraTest.closed)).toBe(1);
  expect(await page.evaluate(() => window.cameraTest.stops)).toBe(1);
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await expect(page.getByText("Camera on · processed locally", { exact: true })).toBeVisible();
});

test("rendered counter counts complete cycles and pauses on tracking loss", async ({ page }) => {
  async function hold(angle, wait = 450) {
    await page.evaluate((angle) => {
      if (angle === null) { window.cameraTest.poses = []; return; }
      const p = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.5, visibility: 0.9, presence: 0.9 }));
      const r = angle * Math.PI / 180;
      // Build a known image-space angle, correcting normalized x for the 4:3 image.
      for (const [shoulder, hip, knee, ankle] of [[11, 23, 25, 27], [12, 24, 26, 28]]) {
        p[knee] = { ...p[knee], x: 0.5, y: 0.5 };
        p[hip] = { ...p[hip], x: 0.5, y: 0.3 };
        p[shoulder] = { ...p[shoulder], x: 0.5, y: 0.1 };
        p[ankle] = { ...p[ankle], x: 0.5 + Math.sin(r) * 0.15, y: 0.5 - Math.cos(r) * 0.2 };
      }
      window.cameraTest.poses = [p];
    }, angle);
    await page.waitForTimeout(wait); // Simulated pose must remain stable across real animation frames.
  }
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await expect(page.getByText("Camera on · processed locally", { exact: true })).toBeVisible();
  await hold(170); await hold(135); await hold(100); await hold(170);
  await expect(page.getByTestId("rep-count")).toHaveText("1");
  await hold(135); await hold(100); await hold(null);
  await expect(page.getByRole("status")).toContainText("Tracking paused");
  await hold(170);
  await expect(page.getByTestId("rep-count")).toHaveText("1");
  await page.getByRole("button", { name: "Reset counts", exact: true }).click();
  await expect(page.getByTestId("rep-count")).toHaveText("0");
});

async function holdMovement(page, id, angle) {
  await page.evaluate(({id,angle}) => {
    const p = Array.from({length:33},()=>({x:.5,y:.5,visibility:.9,presence:.9}));
    const chain = id === "Wall_Press_Up" ? [23,11,13,15] : [11,23,25,27];
    const [anchor,a,b,c]=chain, r=angle*Math.PI/180;
    p[anchor]={...p[anchor], y:id === "Wall_Press_Up" ? .7 : .1};
    p[a]={...p[a],y:.3}; p[b]={...p[b],y:.5};
    p[c]={...p[c],x:.5+Math.sin(r)*.15,y:.5-Math.cos(r)*.2};
    window.cameraTest.poses=[p];
  },{id,angle});
  await page.waitForTimeout(500);
}

for (const id of ["Seated_Knee_Extension","Wall_Press_Up"]) {
  test(`${id} uses its own angles and counts a cycle`,async({page})=>{
    await page.getByLabel("Measured exercise",{exact:true}).selectOption(id);
    await page.getByRole("button",{name:"Start camera",exact:true}).click();
    await expect(page.getByText("Camera on · processed locally",{exact:true})).toBeVisible();
    const angles=id === "Seated_Knee_Extension" ? [90,135,170,90] : [170,135,100,170];
    for (const angle of angles) await holdMovement(page,id,angle);
    await expect(page.getByTestId("rep-count")).toHaveText("1");
  });
}

test("numeric result saves with pain check and reloads in measured progress",async({page})=>{
  const plan={id:1,status:"active",difficulty_level:2,frequency_per_week:3,source:"fallback",start_date:"2026-11-01",items:[{exercise_id:"Bodyweight_Squat",position:0,sets:1,reps:8}],schedule:[]};
  let saved=[];
  await page.route("**/api/plans/current",route=>route.fulfill({json:plan}));
  await page.route("**/api/measurements",route=>route.fulfill({json:saved}));
  await page.route("**/api/sessions",async route=>{
    if(route.request().method()==="POST") {
      const body=route.request().postDataJSON();
      expect(body.pain_after).toBe(2);
      expect(body.completed).toBe(false);
      expect(Object.keys(body.measurements[0]).sort()).toEqual(["exercise_id","protocol","side","reps","partials","hold_seconds","min_angle","max_angle","tracking_ratio","duration_seconds"].sort());
      saved=body.measurements.map((m,i)=>({...m,id:i+1,session_id:1,target_reps:8,created_at:"2026-11-18T12:00:00Z"}));
      await route.fulfill({status:201,json:{id:1}});
    } else await route.fulfill({json:[]});
  });
  await page.route("**/api/notifications",route=>route.fulfill({json:[]}));
  await page.route("**/api/progress",route=>route.fulfill({json:{plan_id:1,weeks:[],explanation:""}}));
  await page.reload();
  await page.getByRole("button",{name:"Start camera",exact:true}).click();
  await expect(page.getByText("Camera on · processed locally",{exact:true})).toBeVisible();
  for (const angle of [170,135,100,170]) await holdMovement(page,"Bodyweight_Squat",angle);
  await page.getByRole("button",{name:"Stop camera",exact:true}).click();
  await page.getByRole("button",{name:"Add stopped result",exact:true}).click();
  const result = page.getByText(/Bodyweight squat: 1 cycles/);
  const original = await result.innerText();
  // Cancelling a restart must preserve the previous recording's tracking quality.
  await page.evaluate(() => { window.cameraTest.delayModel = true; });
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await expect.poll(() => page.evaluate(() => typeof window.cameraTest.resolveModel)).toBe("function");
  await page.getByRole("button", { name: "Stop camera", exact: true }).click();
  await page.evaluate(() => window.cameraTest.resolveModel());
  await page.getByRole("button", { name: "Add stopped result", exact: true }).click();
  await expect(result).toHaveText(original);
  await page.getByLabel("Pain after",{exact:true}).fill("2");
  await page.getByRole("button",{name:"Save measurements and pain check",exact:true}).click();
  await expect(page.getByText("Measurements and pain check saved. Open Progress to see your results.")).toBeVisible();
  await page.goto("/progress");
  await expect(page.getByRole("heading",{name:"Measured movement over time"})).toBeVisible();
  await expect(page.getByRole("cell",{name:"1 / 8",exact:true})).toBeVisible();
  await expect(page.getByRole("img",{name:/Bodyweight squat, left/})).toBeVisible();
});
