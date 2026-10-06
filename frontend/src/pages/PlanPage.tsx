import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import type { Exercise, Plan } from "../types";

export default function PlanPage() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [exercises, setExercises] = useState<Record<string, Exercise>>({});
  const [state, setState] = useState<"loading" | "none" | "ready" | "error">("loading");

  useEffect(() => {
    api.currentPlan()
      .then(async (p) => {
        setPlan(p);
        const list = await Promise.all(p.items.map((i) => api.exercise(i.exercise_id)));
        setExercises(Object.fromEntries(list.map((e) => [e.id, e])));
        setState("ready");
      })
      .catch((err) => setState(err instanceof ApiError && err.status === 404 ? "none" : "error"));
  }, []);

  if (state === "loading") return <p>Loading...</p>;
  if (state === "error") return <p className="text-red-600">Could not load your plan.</p>;
  if (state === "none" || !plan)
    return <p>No plan yet. <Link to="/intake" className="text-teal-700 underline">Start your intake</Link>.</p>;

  const upcoming = plan.schedule.filter((s) => s.scheduled_date >= new Date().toISOString().slice(0, 10)).slice(0, 3);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Your recovery plan</h1>
        <p className="text-sm text-slate-500">
          Level {plan.difficulty_level} · {plan.frequency_per_week}x per week · started {plan.start_date}
        </p>
      </div>
      <section className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-2 font-medium">Next sessions</h2>
        <ul className="text-sm">{upcoming.map((s) => <li key={s.id}>{s.scheduled_date} (week {s.week_index + 1})</li>)}</ul>
      </section>
      <ol className="space-y-4">
        {plan.items.map((item) => {
          const ex = exercises[item.exercise_id];
          return (
            <li key={item.exercise_id} className="rounded-xl bg-white p-4 shadow-sm">
              <div className="flex items-baseline justify-between gap-4">
                <h3 className="font-medium">{item.position + 1}. {ex?.name ?? item.exercise_id}</h3>
                <span className="shrink-0 text-sm text-teal-700">
                  {item.sets} x {item.reps}{ex?.category === "stretching" ? " holds (30s)" : " reps"}
                </span>
              </div>
              {ex && (
                <div className="mt-3 flex flex-col gap-4 sm:flex-row">
                  {ex.media[0] && <img src={ex.media[0]} alt="" className="h-28 w-40 rounded object-cover"
                    onError={(e) => (e.currentTarget.style.display = "none")} />}
                  <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-700">
                    {ex.instructions.map((s, i) => <li key={i}>{s}</li>)}
                  </ol>
                </div>
              )}
            </li>
          );
        })}
      </ol>
      <p className="text-xs text-slate-400">
        Stop any exercise that causes sharp pain. If pain reaches 8/10 or you notice numbness or swelling, see a
        licensed physical therapist.
      </p>
    </div>
  );
}
