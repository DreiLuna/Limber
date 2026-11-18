import { useEffect, useState } from "react";
import { api } from "../api";
import { MOVEMENTS } from "../vision/movementTracker";
import type { MovementId } from "../vision/movementTracker";
import type { SavedMeasurement } from "../types";

export default function MeasuredProgress() {
  const [rows, setRows] = useState<SavedMeasurement[]>([]), [error, setError] = useState("");
  const [exercise, setExercise] = useState<MovementId>("Bodyweight_Squat"), [side, setSide] = useState("left");
  const [metric, setMetric] = useState<"reps" | "hold_seconds" | "span">("reps");
  useEffect(() => { let active = true; api.measurements().then(items => { if (active) setRows(items); }).catch(() => { if (active) setError("Could not load measured results. Reload to try again."); }); return () => { active = false; }; }, []);
  const selected = rows.filter(r => r.exercise_id === exercise && r.side === side);
  const value = (r: SavedMeasurement) => metric === "span" ? r.max_angle - r.min_angle : r[metric];
  const times = selected.map(r => Date.parse(r.created_at)), values = selected.map(value);
  const minTime = Math.min(...times), maxTime = Math.max(...times), maxValue = Math.max(1, ...values);
  const x = (i: number) => times.length === 1 ? 300 : 55 + (times[i] - minTime) / Math.max(1, maxTime - minTime) * 490;
  const y = (i: number) => 170 - values[i] / maxValue * 135;
  const name = metric === "span" ? "Camera angle span (degrees)" : metric === "reps" ? "Completed cycles" : "Time in bent position (seconds)";
  return <section className="rounded-xl bg-white p-5 shadow-sm" aria-labelledby="measured-title">
    <h2 id="measured-title" className="text-lg font-semibold">Measured movement over time</h2>
    <p className="mt-2 text-sm text-slate-600">Saved camera estimates, separated by exercise and side. Angle span is the observed 2D joint-angle range, not a clinical flexibility measurement. Low tracking quality can affect comparisons.</p>
    {error && <p role="alert">{error}</p>}
    <div className="my-4 flex flex-wrap gap-3">
      <label>Exercise <select aria-label="Chart exercise" className="rounded border p-2" value={exercise} onChange={e => setExercise(e.target.value as MovementId)}>{Object.entries(MOVEMENTS).map(([id, info]) => <option key={id} value={id}>{info.name}</option>)}</select></label>
      <label>Side <select aria-label="Chart side" className="rounded border p-2" value={side} onChange={e => setSide(e.target.value)}><option value="left">Left</option><option value="right">Right</option></select></label>
      <label>Measure <select aria-label="Chart measure" className="rounded border p-2" value={metric} onChange={e => setMetric(e.target.value as typeof metric)}><option value="reps">Cycles</option><option value="hold_seconds">Hold time</option><option value="span">Angle span</option></select></label>
    </div>
    {!selected.length ? <p className="text-sm text-slate-500">No saved results for this exercise and side. Add a camera result with your session pain check to begin.</p> : <>
      <svg viewBox="0 0 600 215" role="img" aria-label={`${MOVEMENTS[exercise].name}, ${side}: ${name} over time`} className="w-full max-w-3xl">
        <title>{name} over time</title><path d="M55 25V170H550" fill="none" stroke="#94a3b8" />
        <text x="8" y="38" fontSize="12">{maxValue.toFixed(1)}</text><text x="28" y="172" fontSize="12">0</text>
        <polyline points={values.map((_, i) => `${x(i)},${y(i)}`).join(" ")} stroke="#0f766e" strokeWidth="3" fill="none" />
        {selected.map((r,i) => <circle key={r.id} cx={x(i)} cy={y(i)} r="4" fill={r.tracking_ratio >= .8 ? "#0f766e" : "#b45309"}><title>{new Date(r.created_at).toLocaleString()}: {value(r).toFixed(1)}, {Math.round(r.tracking_ratio*100)}% tracked</title></circle>)}
        <text x="55" y="195" fontSize="12">{new Date(selected[0].created_at).toLocaleDateString()}</text><text x="545" y="195" textAnchor="end" fontSize="12">{new Date(selected.at(-1)!.created_at).toLocaleDateString()}</text>
      </svg>
      <p className="text-sm">{name}. Amber points have less than 80% tracking coverage.</p>
      <div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">Saved measurements for the selected exercise and side</caption><thead><tr>{["Date", "Cycles / target", "Partial", "Bent hold", "Angle span", "Tracked"].map(h => <th className="p-2" key={h}>{h}</th>)}</tr></thead><tbody>{selected.map(r => <tr key={r.id} className="border-t"><td className="p-2">{new Date(r.created_at).toLocaleString()}</td><td>{r.reps} / {r.target_reps}</td><td>{r.partials}</td><td>{r.hold_seconds.toFixed(1)}s</td><td>{(r.max_angle-r.min_angle).toFixed(1)}°</td><td>{Math.round(r.tracking_ratio*100)}%</td></tr>)}</tbody></table></div>
    </>}
    <p className="mt-4 text-sm text-slate-600">Level increases need two completed plan weeks with low pain and consistent measured results from scheduled sessions. Extra practice does not count as scheduled completion. Referral checks always take priority.</p>
  </section>;
}
