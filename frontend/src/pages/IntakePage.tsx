import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import BodyMap from "../components/BodyMap";
import {
  ACTIVITIES, LIMITATIONS, OTHER_REGIONS, RED_FLAGS, RED_FLAG_COPY, SUPPORTED_REGIONS,
  copy, referralText, type Assessment, type BodyRegion,
} from "../types";

type Step = "safety" | "region" | "pain" | "limits" | "activities" | "review";

const PAIN_WORDS = ["No pain", "Very mild", "Mild", "Mild", "Moderate", "Moderate", "Moderate", "Severe", "Severe", "Very severe", "Worst imaginable"];

function painColor(p: number) {
  if (p <= 3) return "text-teal-700";
  if (p <= 6) return "text-amber-600";
  return "text-red-600";
}

function Choice({ selected, onClick, title, hint }: { selected: boolean; onClick: () => void; title: string; hint?: string }) {
  return (
    <button type="button" aria-pressed={selected} onClick={onClick}
      className={`w-full rounded-xl border px-4 py-3 text-left transition-colors ${
        selected ? "border-teal-600 bg-teal-50 ring-2 ring-teal-600/20" : "border-slate-200 bg-white hover:border-slate-300"}`}>
      <span className="flex items-center gap-3">
        <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border text-xs ${
          selected ? "border-teal-700 bg-teal-700 text-white" : "border-slate-300"}`}>{selected && "✓"}</span>
        <span>
          <span className="block font-medium">{title}</span>
          {hint && <span className="block text-sm text-slate-500">{hint}</span>}
        </span>
      </span>
    </button>
  );
}

export default function IntakePage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("safety");
  const [redFlags, setRedFlags] = useState<string[]>([]);
  const [noFlags, setNoFlags] = useState(false);
  const [region, setRegion] = useState<BodyRegion | null>(null);
  const [showOther, setShowOther] = useState(false);
  const [pain, setPain] = useState(3);
  const [limitations, setLimitations] = useState<string[]>([]);
  const [activities, setActivities] = useState<string[]>([]);
  const [description, setDescription] = useState("");
  const [referral, setReferral] = useState<Assessment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // A red flag or unsupported region will be referred no matter what, so skip the plan-only questions.
  // The backend scope check still makes the actual decision.
  const willRefer = redFlags.length > 0 || (region !== null && !(SUPPORTED_REGIONS as readonly string[]).includes(region));
  const steps: Step[] = willRefer ? ["safety", "region", "pain", "review"] : ["safety", "region", "pain", "limits", "activities", "review"];
  const index = steps.indexOf(step);
  const next = () => setStep(steps[index + 1]);
  const back = () => setStep(steps[index - 1]);

  const toggle = (list: string[], set: (v: string[]) => void, v: string) =>
    set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  const canContinue = step === "safety" ? noFlags || redFlags.length > 0 : step === "region" ? region !== null : true;

  async function submit() {
    if (!region) return;
    setBusy(true); setError(null);
    try {
      const a = await api.createAssessment({
        body_region: region, pain_level: pain,
        limitations: willRefer ? [] : limitations,
        activity_difficulties: willRefer ? [] : activities,
        red_flags: redFlags, description: description.trim() || undefined,
      });
      if (!a.in_scope) { setReferral(a); return; }
      await api.createPlan();
      navigate("/plan");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (referral) {
    return (
      <div className="mx-auto max-w-2xl rounded-2xl border border-amber-300 bg-amber-50 p-6 sm:p-8">
        <p className="mb-2 text-sm font-semibold uppercase tracking-wide text-amber-700">Our recommendation</p>
        <h1 className="mb-3 text-2xl font-semibold">Please see a licensed physical therapist</h1>
        <p className="mb-4 text-slate-700">
          Based on your answers, a self-guided plan isn't the safe choice right now. A physical therapist can examine
          you in person and find the right treatment. We did not create an exercise plan.
        </p>
        <h2 className="mb-2 font-medium">Why we're recommending this</h2>
        <ul className="mb-6 list-disc space-y-1 pl-5 text-slate-700">
          {referral.referral_reasons.map((r) => <li key={r}>{referralText(r)}</li>)}
        </ul>
        <p className="mb-6 rounded-lg bg-white p-3 text-sm text-slate-600 ring-1 ring-amber-200">
          If you have sudden severe pain, loss of bladder or bowel control, or numbness that is spreading, seek
          emergency care right away.
        </p>
        <button className="text-sm font-medium text-teal-700 hover:underline"
          onClick={() => { setReferral(null); setStep("safety"); }}>
          Start the check-in again
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <div className="mb-2 flex justify-between text-xs font-medium text-slate-500">
          <span>Check-in</span>
          <span>Step {index + 1} of {steps.length}</span>
        </div>
        <div className="h-2 rounded-full bg-slate-200">
          <div className="h-2 rounded-full bg-teal-600 transition-all" style={{ width: `${((index + 1) / steps.length) * 100}%` }} />
        </div>
      </div>

      <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200 sm:p-8">
        {step === "safety" && (
          <>
            <h1 className="text-2xl font-semibold">First, a quick safety check</h1>
            <p className="mb-5 mt-1 text-slate-500">Are you experiencing any of these? Select all that apply.</p>
            <div className="space-y-3">
              {RED_FLAGS.map((f) => (
                <Choice key={f} title={RED_FLAG_COPY[f].title} hint={RED_FLAG_COPY[f].hint}
                  selected={redFlags.includes(f)}
                  onClick={() => { toggle(redFlags, setRedFlags, f); setNoFlags(false); }} />
              ))}
              <Choice title="None of these" selected={noFlags} onClick={() => { setNoFlags(!noFlags); setRedFlags([]); }} />
            </div>
          </>
        )}

        {step === "region" && (
          <>
            <h1 className="text-2xl font-semibold">Where does it hurt?</h1>
            <p className="mb-5 mt-1 text-slate-500">Tap the figure or pick from the list. Choose the area that bothers you most.</p>
            <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-start">
              <BodyMap value={region} onSelect={(r) => { setRegion(r); setShowOther(false); }} />
              <div className="w-full space-y-3">
                {SUPPORTED_REGIONS.map((r) => (
                  <Choice key={r} title={copy(r)} selected={region === r} onClick={() => { setRegion(r); setShowOther(false); }} />
                ))}
                <button type="button" className="text-sm font-medium text-teal-700 hover:underline"
                  onClick={() => setShowOther(!showOther)}>
                  {showOther ? "Hide other areas" : "It's somewhere else"}
                </button>
                {showOther && (
                  <div className="grid grid-cols-2 gap-2">
                    {OTHER_REGIONS.map((r) => (
                      <Choice key={r} title={copy(r)} selected={region === r} onClick={() => setRegion(r)} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {step === "pain" && (
          <>
            <h1 className="text-2xl font-semibold">How much does it hurt right now?</h1>
            <p className="mb-8 mt-1 text-slate-500">0 means no pain. 10 is the worst pain you can imagine.</p>
            <div className="mb-6 text-center">
              <span className={`text-6xl font-bold ${painColor(pain)}`}>{pain}</span>
              <span className="text-2xl text-slate-400"> / 10</span>
              <p className={`mt-1 font-medium ${painColor(pain)}`}>{PAIN_WORDS[pain]}</p>
            </div>
            <input type="range" min={0} max={10} value={pain} aria-label="Pain level"
              onChange={(e) => setPain(+e.target.value)} className="w-full accent-teal-700" />
            <div className="mt-1 flex justify-between text-xs text-slate-500"><span>No pain</span><span>Worst imaginable</span></div>
          </>
        )}

        {step === "limits" && (
          <>
            <h1 className="text-2xl font-semibold">Is there anything you can't do?</h1>
            <p className="mb-5 mt-1 text-slate-500">We'll leave out exercises that need these. Skip this if none apply.</p>
            <div className="space-y-3">
              {LIMITATIONS.map((l) => (
                <Choice key={l} title={copy(l)} selected={limitations.includes(l)} onClick={() => toggle(limitations, setLimitations, l)} />
              ))}
            </div>
          </>
        )}

        {step === "activities" && (
          <>
            <h1 className="text-2xl font-semibold">What's hard to do right now?</h1>
            <p className="mb-5 mt-1 text-slate-500">We'll favor exercises that help with these.</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {ACTIVITIES.map((a) => (
                <Choice key={a} title={copy(a)} selected={activities.includes(a)} onClick={() => toggle(activities, setActivities, a)} />
              ))}
            </div>
          </>
        )}

        {step === "review" && (
          <>
            <h1 className="text-2xl font-semibold">Review your answers</h1>
            <p className="mb-5 mt-1 text-slate-500">Tap any answer to change it.</p>
            <dl className="divide-y divide-slate-200 rounded-xl ring-1 ring-slate-200">
              {([
                ["safety", "Safety check", redFlags.length ? redFlags.map((f) => RED_FLAG_COPY[f].title).join(", ") : "None of these"],
                ["region", "Where it hurts", region ? copy(region) : ""],
                ["pain", "Pain right now", `${pain} / 10 (${PAIN_WORDS[pain].toLowerCase()})`],
                ...(willRefer ? [] : [
                  ["limits", "Can't do", limitations.length ? limitations.map(copy).join(", ") : "Nothing listed"],
                  ["activities", "Hard right now", activities.length ? activities.map(copy).join(", ") : "Nothing listed"],
                ]),
              ] as [Step, string, string][]).map(([s, title, value]) => (
                <button key={s} type="button" onClick={() => setStep(s)}
                  className="flex w-full justify-between gap-4 px-4 py-3 text-left hover:bg-slate-50">
                  <dt className="text-sm text-slate-500">{title}</dt>
                  <dd className="text-right text-sm font-medium">{value}</dd>
                </button>
              ))}
            </dl>
            <label className="mt-5 block">
              <span className="mb-1 block text-sm font-medium">Anything else we should know? <span className="text-slate-400">(optional)</span></span>
              <textarea className="w-full rounded-lg border border-slate-300 px-3 py-2" rows={3} maxLength={2000}
                placeholder="For example: started after a long run last week"
                value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
            {error && <p role="alert" className="mt-4 text-sm text-red-600">{error}</p>}
          </>
        )}

        <div className="mt-8 flex items-center justify-between">
          {index > 0
            ? <button type="button" onClick={back} className="rounded-lg px-4 py-2 text-slate-600 hover:bg-slate-100">Back</button>
            : <Link to="/library" className="text-sm text-slate-500 hover:underline">Browse library instead</Link>}
          {step === "review"
            ? <button type="button" onClick={submit} disabled={busy}
                className="rounded-lg bg-teal-700 px-6 py-2.5 font-medium text-white hover:bg-teal-800 disabled:opacity-50">
                {busy ? "Building your plan..." : "Get my plan"}
              </button>
            : <button type="button" onClick={next} disabled={!canContinue}
                className="rounded-lg bg-teal-700 px-6 py-2.5 font-medium text-white hover:bg-teal-800 disabled:opacity-40">
                Continue
              </button>}
        </div>
      </div>
    </div>
  );
}
