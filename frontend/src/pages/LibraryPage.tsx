import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useFavorites } from "../favorites";
import { SUPPORTED_REGIONS, copy, label, type Assessment, type Exercise } from "../types";

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" aria-pressed={active} onClick={onClick}
      className={`shrink-0 rounded-full border px-3 py-1.5 text-sm transition-colors ${
        active ? "border-teal-700 bg-teal-700 text-white" : "border-slate-300 bg-white text-slate-700 hover:border-slate-400"}`}>
      {children}
    </button>
  );
}

export function Heart({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button type="button" aria-pressed={on} aria-label={on ? "Remove from favorites" : "Save to favorites"}
      onClick={(e) => { e.preventDefault(); onClick(); }}
      className="flex h-9 w-9 items-center justify-center rounded-full bg-white/90 text-lg shadow ring-1 ring-slate-200 hover:scale-105">
      <span className={on ? "text-rose-500" : "text-slate-400"}>{on ? "♥" : "♡"}</span>
    </button>
  );
}

// Same order as backend/app/modules/recommendation/filtering.py (exact difficulty mode),
// used only to highlight exercises. The plan itself is always built by the backend.
function matchesIntake(e: Exercise, a: Assessment) {
  return e.body_regions.includes(a.body_region)
    && !e.contraindications.some((c) => a.limitations.includes(c))
    && e.difficulty === a.starting_difficulty;
}

export default function LibraryPage({ signedIn }: { signedIn: boolean }) {
  const [exercises, setExercises] = useState<Exercise[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [region, setRegion] = useState<string | null>(null);
  const [level, setLevel] = useState<number | null>(null);
  const [category, setCategory] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [onlyFavorites, setOnlyFavorites] = useState(false);
  const [onlyMatches, setOnlyMatches] = useState(false);
  const favorites = useFavorites();

  useEffect(() => {
    api.exercises().then(setExercises).catch(() => setFailed(true));
    if (signedIn) api.latestAssessment().then((a) => a.in_scope && setAssessment(a)).catch(() => {});
  }, [signedIn]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (exercises ?? []).filter((e) =>
      (!region || e.body_regions.includes(region))
      && (!level || e.difficulty === level)
      && (!category || e.category === category)
      && (!q || e.name.toLowerCase().includes(q))
      && (!onlyFavorites || favorites.has(e.id))
      && (!onlyMatches || (assessment !== null && matchesIntake(e, assessment))));
  }, [exercises, region, level, category, query, onlyFavorites, onlyMatches, assessment, favorites]);

  const categories = useMemo(() => [...new Set((exercises ?? []).map((e) => e.category))].sort(), [exercises]);

  return (
    <div>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Exercise library</h1>
          <p className="mt-1 text-slate-500">Low-intensity exercises for the lower back, shoulder, knee, and ankle.</p>
        </div>
        <input type="search" placeholder="Search exercises" value={query} onChange={(e) => setQuery(e.target.value)}
          className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 sm:w-64" />
      </div>

      {assessment && (
        <button type="button" onClick={() => setOnlyMatches(!onlyMatches)} aria-pressed={onlyMatches}
          className={`mb-4 flex w-full items-center justify-between rounded-xl px-4 py-3 text-left ring-1 transition-colors ${
            onlyMatches ? "bg-teal-700 text-white ring-teal-700" : "bg-teal-50 text-teal-900 ring-teal-200 hover:bg-teal-100"}`}>
          <span>
            <span className="block font-medium">Matches your check-in</span>
            <span className={`text-sm ${onlyMatches ? "text-teal-100" : "text-teal-700"}`}>
              {copy(assessment.body_region)} · Level {assessment.starting_difficulty} · leaves out what you can't do
            </span>
          </span>
          <span className="text-sm font-medium">{onlyMatches ? "Showing" : "Show"}</span>
        </button>
      )}

      <div className="mb-6 space-y-3">
        <div className="flex gap-2 overflow-x-auto pb-1">
          <Chip active={!region} onClick={() => setRegion(null)}>All areas</Chip>
          {SUPPORTED_REGIONS.map((r) => <Chip key={r} active={region === r} onClick={() => setRegion(region === r ? null : r)}>{copy(r)}</Chip>)}
        </div>
        <div className="flex flex-wrap gap-2">
          {[1, 2, 3].map((l) => <Chip key={l} active={level === l} onClick={() => setLevel(level === l ? null : l)}>Level {l}</Chip>)}
          <span className="mx-1 hidden w-px bg-slate-200 sm:block" />
          {categories.map((c) => <Chip key={c} active={category === c} onClick={() => setCategory(category === c ? null : c)}>{label(c)}</Chip>)}
          <span className="mx-1 hidden w-px bg-slate-200 sm:block" />
          <Chip active={onlyFavorites} onClick={() => setOnlyFavorites(!onlyFavorites)}>♥ Saved ({favorites.ids.length})</Chip>
        </div>
      </div>

      {failed && <p className="text-red-600">Could not load the library. Is the backend running?</p>}
      {!exercises && !failed && <p className="text-slate-500">Loading exercises...</p>}
      {exercises && (
        <>
          <p className="mb-3 text-sm text-slate-500">{shown.length} exercise{shown.length === 1 ? "" : "s"}</p>
          {shown.length === 0 ? (
            <p className="rounded-xl bg-white p-8 text-center text-slate-500 ring-1 ring-slate-200">
              Nothing matches those filters. Try removing one.
            </p>
          ) : (
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {shown.map((e) => (
                <li key={e.id}>
                  <Link to={`/library/${encodeURIComponent(e.id)}`}
                    className="group block overflow-hidden rounded-2xl bg-white ring-1 ring-slate-200 transition-shadow hover:shadow-md">
                    <div className="relative aspect-[4/3] bg-slate-100">
                      {e.media[0] && <img src={e.media[0]} alt="" loading="lazy" className="h-full w-full object-cover"
                        onError={(ev) => (ev.currentTarget.style.display = "none")} />}
                      <div className="absolute right-3 top-3"><Heart on={favorites.has(e.id)} onClick={() => favorites.toggle(e.id)} /></div>
                    </div>
                    <div className="p-4">
                      <h2 className="font-medium group-hover:text-teal-700">{e.name}</h2>
                      <p className="mt-1 text-sm text-slate-500">
                        {e.body_regions.map(copy).join(", ")} · Level {e.difficulty} · {label(e.category)}
                      </p>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
