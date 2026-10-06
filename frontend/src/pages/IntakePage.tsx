import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { ACTIVITIES, BODY_REGIONS, LIMITATIONS, RED_FLAGS, label, type Assessment, type BodyRegion } from "../types";

function Checks({ title, options, value, onChange }: {
  title: string; options: readonly string[]; value: string[]; onChange: (v: string[]) => void;
}) {
  const toggle = (o: string) => onChange(value.includes(o) ? value.filter((x) => x !== o) : [...value, o]);
  return (
    <fieldset>
      <legend className="mb-2 font-medium">{title}</legend>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {options.map((o) => (
          <label key={o} className="flex items-center gap-2 rounded border bg-white px-3 py-2 text-sm">
            <input type="checkbox" checked={value.includes(o)} onChange={() => toggle(o)} />
            {label(o)}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export default function IntakePage() {
  const navigate = useNavigate();
  const [region, setRegion] = useState<BodyRegion>("lower_back");
  const [pain, setPain] = useState(4);
  const [limitations, setLimitations] = useState<string[]>([]);
  const [activities, setActivities] = useState<string[]>([]);
  const [redFlags, setRedFlags] = useState<string[]>([]);
  const [description, setDescription] = useState("");
  const [referral, setReferral] = useState<Assessment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const a = await api.createAssessment({
        body_region: region, pain_level: pain, limitations, activity_difficulties: activities,
        red_flags: redFlags, description: description || undefined,
      });
      if (!a.in_scope) { setReferral(a); return; }
      await api.createPlan();
      navigate("/plan");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  if (referral) {
    return (
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-6">
        <h1 className="mb-2 text-xl font-semibold">Please see a licensed physical therapist</h1>
        <p className="mb-4 text-sm">
          Based on what you reported, LIMBER is not the right fit. A licensed physical therapist can assess
          this safely. We did not create an exercise plan.
        </p>
        <ul className="mb-4 list-disc pl-5 text-sm text-slate-700">
          {referral.referral_reasons.map((r) => <li key={r}>{label(r.replace(":", ": "))}</li>)}
        </ul>
        <button className="text-sm text-teal-700 hover:underline" onClick={() => setReferral(null)}>Back to intake</button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Tell us about your pain</h1>
        <p className="text-sm text-slate-500">This takes about 2 minutes. LIMBER covers minor lower back, shoulder, knee, and ankle pain.</p>
      </div>

      <label className="block">
        <span className="mb-2 block font-medium">Where does it hurt?</span>
        <select className="w-full rounded border bg-white px-3 py-2" value={region}
          onChange={(e) => setRegion(e.target.value as BodyRegion)}>
          {BODY_REGIONS.map((r) => <option key={r} value={r}>{label(r)}</option>)}
        </select>
      </label>

      <label className="block">
        <span className="mb-2 block font-medium">Pain right now: <b>{pain}</b> / 10</span>
        <input type="range" min={0} max={10} value={pain} onChange={(e) => setPain(+e.target.value)} className="w-full" />
      </label>

      <Checks title="Anything you can't do?" options={LIMITATIONS} value={limitations} onChange={setLimitations} />
      <Checks title="What activities are hard right now?" options={ACTIVITIES} value={activities} onChange={setActivities} />
      <Checks title="Are you experiencing any of these?" options={RED_FLAGS} value={redFlags} onChange={setRedFlags} />

      <label className="block">
        <span className="mb-2 block font-medium">Anything else? <span className="text-slate-400">(optional)</span></span>
        <textarea className="w-full rounded border px-3 py-2" rows={3} value={description}
          onChange={(e) => setDescription(e.target.value)} />
      </label>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <button disabled={busy} className="rounded bg-teal-700 px-5 py-2 font-medium text-white hover:bg-teal-800 disabled:opacity-50">
        {busy ? "Building your plan..." : "Get my plan"}
      </button>
    </form>
  );
}
