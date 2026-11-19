import { useEffect, useRef, useState } from "react";
import type { PoseLandmarker } from "@mediapipe/tasks-vision";
import { MovementTracker, MOVEMENTS, readMovementPose } from "../vision/movementTracker";
import type { MovementId, Side } from "../vision/movementTracker";
import MeasurementSave from "../components/MeasurementSave";

const WASM_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.3/wasm";
const MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";

function cameraError(error: unknown): string {
  const name = error instanceof Error ? error.name : "";
  if (name === "NotAllowedError") return "Camera access was denied. Allow camera access for this site in your browser settings, then try again.";
  if (name === "NotFoundError") return "No camera was found. Connect a camera and try again.";
  if (name === "NotReadableError") return "The camera is busy or unavailable. Close other apps using it and try again.";
  return "Could not start movement tracking. Check your connection for the model download, and try Chrome or Safari on localhost or HTTPS.";
}

export default function CameraPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const counter = useRef(new MovementTracker());
  const stream = useRef<MediaStream | null>(null);
  const detector = useRef<PoseLandmarker | null>(null);
  const frame = useRef(0);
  const generation = useRef(0);
  const [status, setStatus] = useState<"off" | "loading" | "running">("off");
  const [result, setResult] = useState(() => counter.current.reset());
  const [error, setError] = useState<string | null>(null);

  const [movement, setMovement] = useState<MovementId>("Bodyweight_Squat");
  const [side, setSide] = useState<Side>("left");
  const [held, setHeld] = useState(0);
  function selectMovement(id: MovementId, selectedSide: Side) {
    counter.current = new MovementTracker(id, selectedSide);
    setMovement(id); setSide(selectedSide); setResult(counter.current.reset()); setHeld(0);
  }

  function release() {
    generation.current++;
    cancelAnimationFrame(frame.current);
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    detector.current?.close();
    detector.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    const canvas = canvasRef.current;
    canvas?.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
  }

  function stop() {
    release();
    setStatus("off");
    setResult(counter.current.update(null, performance.now()));
  }

  useEffect(() => {
    const onHidden = () => { if (document.hidden) stop(); };
    document.addEventListener("visibilitychange", onHidden);
    return () => { document.removeEventListener("visibilitychange", onHidden); release(); };
  }, []);

  async function start() {
    if (status !== "off") return;
    setError(null);
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setError("Camera access needs HTTPS or localhost. On your Mac, open http://localhost:5173/camera.");
      return;
    }
    setStatus("loading");
    const run = ++generation.current;
    let stage = "camera";
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } }, audio: false,
      });
      if (generation.current !== run) { media.getTracks().forEach((track) => track.stop()); return; }
      stream.current = media;
      const video = videoRef.current!;
      video.srcObject = media;
      await video.play();
      if (generation.current !== run) return;
      stage = "model";
      const { FilesetResolver, PoseLandmarker } = await import("@mediapipe/tasks-vision");
      const vision = await FilesetResolver.forVisionTasks(WASM_URL);
      if (generation.current !== run) return;
      const model = await PoseLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: MODEL_URL, delegate: "CPU" },
        runningMode: "VIDEO", numPoses: 2,
        minPoseDetectionConfidence: 0.65, minPosePresenceConfidence: 0.65, minTrackingConfidence: 0.65,
      });
      if (generation.current !== run) { model.close(); return; }
      detector.current = model;
      let lastVideoTime = -1;
      let lastFrameTime = 0;
      const began = performance.now();
      setResult(counter.current.reset());
      setStatus("running");
      media.getVideoTracks().forEach((track) => track.addEventListener("ended", () => {
        if (generation.current === run) { stop(); setError("The camera disconnected. Reconnect it and start again."); }
      }, { once: true }));

      function tick(now: number) {
        if (generation.current !== run) return;
        try {
          if (now - began >= 1_800_000) { stop(); setError("This recording reached the 30-minute limit. Save your result or start another set."); return; }
          if (video.readyState >= 2 && video.currentTime !== lastVideoTime && now - lastFrameTime >= 80) {
            lastVideoTime = video.currentTime;
            lastFrameTime = now;
            const poses = model.detectForVideo(video, now);
            const sample = readMovementPose(movement, poses.landmarks, video.videoWidth, video.videoHeight, side);
            setResult(counter.current.update(sample, now));
            setHeld(counter.current.summary()?.hold_seconds ?? 0);
            const canvas = canvasRef.current;
            if (canvas) {
              canvas.width = video.videoWidth;
              canvas.height = video.videoHeight;
              const ctx = canvas.getContext("2d");
              if (ctx && sample) {
                ctx.strokeStyle = "#2dd4bf";
                ctx.fillStyle = "#ffffff";
                ctx.lineWidth = 5;
                ctx.beginPath();
                sample.points.forEach((point, index) => {
                  const x = point.x * canvas.width, y = point.y * canvas.height;
                  if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                });
                ctx.stroke();
                sample.points.forEach((point) => {
                  ctx.beginPath(); ctx.arc(point.x * canvas.width, point.y * canvas.height, 6, 0, 2 * Math.PI); ctx.fill();
                });
              }
            }
          } else if (now - lastFrameTime > 400) {
            setResult(counter.current.update(null, now));
            const canvas = canvasRef.current;
            canvas?.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
          }
          frame.current = requestAnimationFrame(tick);
        } catch {
          stop(); setError("Tracking stopped unexpectedly. Your video has not been saved. Try starting again.");
        }
      }
      frame.current = requestAnimationFrame(tick);
    } catch (err) {
      if (generation.current !== run) return;
      release(); setStatus("off");
      setError(stage === "camera" ? cameraError(err) : "The camera opened, but the pose model could not load. Check your internet connection and try again.");
    }
  }

  return <div className="mx-auto max-w-4xl">
    <p className="text-sm font-semibold uppercase tracking-wide text-teal-700">Camera lab · prototype</p>
    <h1 className="mt-2 text-3xl font-semibold">See your movement, count each cycle</h1>
    <p className="mt-3 max-w-2xl text-slate-600">Camera feedback for three exercises. It estimates movement from a side view; it does not assess exercise safety or technique. Only try movements you are already cleared to do. Stop if you feel pain.</p>
    <div className="mt-5 flex flex-wrap gap-4">
      <label>Exercise <select aria-label="Measured exercise" disabled={status !== "off"} value={movement} onChange={e => selectMovement(e.target.value as MovementId, side)} className="ml-2 rounded border p-2">{Object.entries(MOVEMENTS).map(([id, info]) => <option key={id} value={id}>{info.name}</option>)}</select></label>
      <label>Visible side <select aria-label="Visible side" disabled={status !== "off"} value={side} onChange={e => selectMovement(movement, e.target.value as Side)} className="ml-2 rounded border p-2"><option value="left">Left</option><option value="right">Right</option></select></label>
    </div>
    <p className="mt-3 text-sm">{MOVEMENTS[movement].view}</p>
    <div className="mt-6 grid gap-5 md:grid-cols-[minmax(0,1fr)_15rem]">
      <section aria-label="Camera preview" className="relative overflow-hidden rounded-2xl bg-slate-950 ring-1 ring-slate-200">
        <video ref={videoRef} autoPlay muted playsInline aria-label="Live camera" className="aspect-[4/3] w-full -scale-x-100 object-contain" />
        <canvas ref={canvasRef} aria-hidden="true" className="pointer-events-none absolute inset-0 h-full w-full -scale-x-100" />
        {status === "off" && <div className="absolute inset-0 flex items-center justify-center px-8 text-center text-slate-300">Your camera preview appears here after you select Start camera.</div>}
        <span className="absolute left-3 top-3 rounded-full bg-slate-950/80 px-3 py-1 text-xs font-medium text-white">{status === "running" ? "Camera on · processed locally" : status === "loading" ? "Starting camera and loading model…" : "Camera off"}</span>
      </section>
      <section aria-label="Movement counts" className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
        <p className="text-sm text-slate-500">Completed cycles</p>
        <p className="mt-1 text-6xl font-semibold text-teal-800" data-testid="rep-count">{result.reps}</p>
        <p className="mt-5 text-sm text-slate-500">Partial / too-fast attempts</p>
        <p className="text-2xl font-semibold" data-testid="partial-count">{result.partials}</p>
        <p className="mt-5 text-sm text-slate-500">Estimated {MOVEMENTS[movement].joint.toLowerCase()} angle</p>
        <p className="text-2xl font-semibold">{status === "running" && result.angle !== null ? `${Math.round(result.angle)}°` : "—"}</p>
        <p className="mt-3 text-sm">Time in end position: {held.toFixed(1)}s</p>
        <p role="status" className="mt-4 text-sm text-slate-700">{status === "off" ? "Camera is off." : status === "loading" ? "Allow camera access when your browser asks. The model may take a moment to download." : result.message}</p>
      </section>
    </div>
    {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    <div className="mt-5 flex flex-wrap gap-3">
      <button onClick={() => void start()} disabled={status !== "off"} className="rounded-lg bg-teal-700 px-5 py-2.5 font-medium text-white hover:bg-teal-800 disabled:opacity-40">Start camera</button>
      <button onClick={stop} disabled={status === "off"} className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 font-medium hover:bg-slate-50 disabled:opacity-40">Stop camera</button>
      <button onClick={() => { setResult(counter.current.reset()); setHeld(0); }} disabled={status === "loading"} className="rounded-lg px-5 py-2.5 text-slate-600 hover:bg-slate-100 disabled:opacity-40">Reset counts</button>
    </div>
    <MeasurementSave summary={() => counter.current.summary()} stopped={status === "off"} />
    <div className="mt-6 grid gap-5 rounded-2xl bg-white p-5 text-sm text-slate-600 ring-1 ring-slate-200 sm:grid-cols-2">
      <div><h2 className="font-semibold text-slate-900">Set up your view</h2><p className="mt-2">Place the camera steadily at about hip height. Use the setup shown for the selected exercise. Use good lighting and keep only one person in frame. Start standing; a partial movement or interrupted view will not count as a full cycle.</p></div>
      <div><h2 className="font-semibold text-slate-900">Your camera stays local</h2><p className="mt-2">Frames are processed in this browser. No video, photos or landmark coordinates are uploaded or stored. Starting downloads a pose model from Google and runtime files from jsDelivr. Counts reset on restart. Only numeric summaries are saved when you choose Save.</p></div>
    </div>
  </div>;
}
