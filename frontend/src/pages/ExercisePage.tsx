import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { useFavorites } from "../favorites";
import { copy, label, type Exercise } from "../types";
import { Heart } from "./LibraryPage";

export default function ExercisePage() {
  const { id = "" } = useParams();
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "missing" | "error">("loading");
  const favorites = useFavorites();

  useEffect(() => {
    setState("loading");
    api.exercise(id)
      .then((e) => { setExercise(e); setState("ready"); })
      .catch((err) => setState(err instanceof ApiError && err.status === 404 ? "missing" : "error"));
  }, [id]);

  const backLink = <Link to="/library" className="text-sm text-teal-700 hover:underline">← Back to library</Link>;
  if (state === "loading") return <p className="text-slate-500">Loading...</p>;
  if (state !== "ready" || !exercise)
    return <div className="space-y-3"><p>{state === "missing" ? "That exercise isn't in the library." : "Could not load this exercise."}</p>{backLink}</div>;

  const e = exercise;
  const isStretch = e.category === "stretching";
  const range = (a: number, b: number) => (a === b ? `${a}` : `${a}–${b}`);

  return (
    <article className="mx-auto max-w-3xl space-y-6">
      {backLink}
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">{e.name}</h1>
          <p className="mt-1 text-slate-500">
            {e.body_regions.map(copy).join(", ")} · Level {e.difficulty} · {label(e.category)}
            {e.equipment && ` · ${label(e.equipment)}`}
          </p>
        </div>
        <Heart on={favorites.has(e.id)} onClick={() => favorites.toggle(e.id)} />
      </header>

      {e.media.length > 0 && (
        <div className="grid grid-cols-2 gap-3">
          {e.media.slice(0, 2).map((src, i) => (
            <figure key={src} className="overflow-hidden rounded-xl bg-slate-100 ring-1 ring-slate-200">
              <img src={src} alt={`${e.name}, ${i === 0 ? "starting" : "ending"} position`} className="aspect-[4/3] w-full object-cover"
                onError={(ev) => (ev.currentTarget.style.display = "none")} />
              <figcaption className="px-3 py-2 text-xs text-slate-500">{i === 0 ? "Start" : "Finish"}</figcaption>
            </figure>
          ))}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
          <p className="text-sm text-slate-500">Typical amount</p>
          <p className="text-lg font-medium">
            {range(e.sets_min, e.sets_max)} sets × {range(e.reps_min, e.reps_max)} {isStretch ? "holds (about 30 seconds)" : "reps"}
          </p>
          <p className="mt-1 text-xs text-slate-500">Your plan sets the exact amount for you.</p>
        </div>
        {e.targets_activities.length > 0 && (
          <div className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
            <p className="text-sm text-slate-500">Helps with</p>
            <p className="font-medium">{e.targets_activities.map(copy).join(", ")}</p>
          </div>
        )}
      </div>

      <section className="rounded-xl bg-white p-5 ring-1 ring-slate-200">
        <h2 className="mb-3 text-lg font-medium">How to do it</h2>
        <ol className="list-decimal space-y-2 pl-5 text-slate-700">
          {e.instructions.map((s, i) => <li key={i}>{s}</li>)}
        </ol>
      </section>

      {e.contraindications.length > 0 && (
        <section className="rounded-xl bg-amber-50 p-5 ring-1 ring-amber-200">
          <h2 className="mb-2 font-medium text-amber-900">Skip this one if</h2>
          <ul className="list-disc space-y-1 pl-5 text-amber-900">
            {e.contraindications.map((c) => <li key={c}>{copy(c).replace(/^I /, "you ").replace(/^My /, "your ")}</li>)}
          </ul>
        </section>
      )}

      <p className="text-sm text-slate-500">
        Move slowly and stop if you feel sharp pain. If pain reaches 8/10, or you notice numbness or swelling, see a licensed
        physical therapist.
      </p>
    </article>
  );
}
