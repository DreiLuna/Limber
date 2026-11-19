import { useEffect, useState } from "react";
import { api } from "../api";
import { RED_FLAGS, label } from "../types";
import type { Plan } from "../types";
import { MOVEMENTS } from "../vision/movementTracker";
import type { MovementSummary } from "../vision/movementTracker";

export default function MeasurementSave({ summary, stopped }: { summary: () => MovementSummary | null; stopped: boolean }) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [drafts, setDrafts] = useState<MovementSummary[]>([]);
  const [before, setBefore] = useState(3), [after, setAfter] = useState(3);
  const [flags, setFlags] = useState<string[]>([]);
  const [completed, setCompleted] = useState(false), [scheduled, setScheduled] = useState("");
  const [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { let active = true; api.currentPlan().then(p => { if (active) setPlan(p); }).catch(() => {}); return () => { active = false; }; }, []);
  function add() {
    setError(""); setMessage("");
    const row = summary();
    if (!row) { setError("Track for at least one second before adding a result."); return; }
    if (!plan?.items.some(p => p.exercise_id === row.exercise_id)) { setError("Practice only: this exercise is not in your active plan."); return; }
    setDrafts(current => [...current.filter(r => r.exercise_id !== row.exercise_id), row]);
    setMessage("Result added. Save with your pain check when finished.");
  }
  async function save(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      await api.logSession({ scheduled_session_id: scheduled ? Number(scheduled) : null,
        completed, pain_before: before, pain_after: after, perceived_difficulty: 3,
        new_red_flags: flags, measurements: drafts });
      setDrafts([]); setFlags([]); setScheduled(""); setCompleted(false);
      setMessage("Measurements and pain check saved. Open Progress to see your results.");
      setPlan(await api.currentPlan().catch(() => null));
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save. Your results are still here; try again."); }
    finally { setBusy(false); }
  }
  const today = new Date();
  const date = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,"0")}-${String(today.getDate()).padStart(2,"0")}`;
  return <section className="mt-6 rounded-2xl bg-white p-5 ring-1 ring-slate-200" aria-label="Save measurements">
    <h2 className="text-lg font-semibold">Save measured progress</h2>
    <p className="mt-2 text-sm text-slate-600">Video stays on this device. Save sends only exercise counts, angle range, hold time, tracking quality and your pain check. Only exercises in your active plan can be saved. Stop and add a result before restarting or changing exercises.</p>
    <button onClick={add} disabled={!stopped || busy} className="my-3 rounded border px-4 py-2 disabled:opacity-40">Add stopped result</button>
    {drafts.map(row => <p key={row.exercise_id} className="text-sm">{MOVEMENTS[row.exercise_id].name}: {row.reps} cycles · {Math.round(row.min_angle)}–{Math.round(row.max_angle)}° · {row.hold_seconds.toFixed(1)}s · {Math.round(row.tracking_ratio * 100)}% tracked <button className="underline" disabled={busy} onClick={() => setDrafts(rows => rows.filter(r => r.exercise_id !== row.exercise_id))}>Remove {MOVEMENTS[row.exercise_id].name}</button></p>)}
    {message && <p className="mt-2 text-teal-800">{message}</p>}{error && <p role="alert" className="mt-2 text-red-800">{error}</p>}
    <form onSubmit={e => void save(e)} className="mt-4 space-y-3">
      <label className="block">Scheduled session <select aria-label="Scheduled session" className="ml-2 rounded border p-2" value={scheduled} onChange={e => setScheduled(e.target.value)}><option value="">Extra practice session</option>{plan?.schedule.filter(s => s.scheduled_date <= date).map(s => <option key={s.id} value={s.id}>{s.scheduled_date}</option>)}</select></label>
      <div className="flex flex-wrap gap-4"><label>Pain before <input aria-label="Pain before" className="w-16 rounded border p-2" type="number" min="0" max="10" required value={before} onChange={e => setBefore(Number(e.target.value))} /></label><label>Pain after <input aria-label="Pain after" className="w-16 rounded border p-2" type="number" min="0" max="10" required value={after} onChange={e => setAfter(Number(e.target.value))} /></label></div>
      <fieldset><legend>New warning symptoms</legend>{RED_FLAGS.map(flag => <label className="mr-4 inline-block text-sm" key={flag}><input type="checkbox" checked={flags.includes(flag)} onChange={() => setFlags(current => current.includes(flag) ? current.filter(f => f !== flag) : [...current, flag])} /> {label(flag)}</label>)}</fieldset>
      <label className="block text-sm"><input type="checkbox" checked={completed} onChange={e => setCompleted(e.target.checked)} /> I completed the whole planned session, including exercises without camera tracking</label>
      <button disabled={!drafts.length || busy || !stopped} className="rounded bg-teal-700 px-4 py-2 text-white disabled:opacity-40">{busy ? "Saving…" : "Save measurements and pain check"}</button>
    </form>
  </section>;
}
