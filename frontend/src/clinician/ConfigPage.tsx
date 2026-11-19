import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { RED_FLAGS, SUPPORTED_REGIONS, label } from "../types";
import { clinicianApi, errorList, type ActiveConfig, type Diff, type Thresholds, type VersionSummary } from "./api";

type Reeval = Thresholds["reevaluation"];

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

function flatten(o: unknown, prefix = ""): Record<string, unknown> {
  if (o === null || typeof o !== "object" || Array.isArray(o)) return { [prefix]: o };
  return Object.entries(o as Record<string, unknown>).reduce<Record<string, unknown>>(
    (acc, [k, v]) => ({ ...acc, ...flatten(v, prefix ? `${prefix}.${k}` : k) }), {});
}

function changes(a: Thresholds, b: Thresholds) {
  const fa = flatten(a), fb = flatten(b);
  return [...new Set([...Object.keys(fa), ...Object.keys(fb)])].sort()
    .filter((k) => JSON.stringify(fa[k]) !== JSON.stringify(fb[k]))
    .map((path) => ({ path, before: fa[path], after: fb[path] }));
}

const show = (v: unknown) => (Array.isArray(v)
  ? v.map((x) => (typeof x === "object" ? `${(x as { min_pain: number }).min_pain}–${(x as { max_pain: number }).max_pain}→L${(x as { level: number }).level}` : label(String(x)))).join(", ")
  : String(v));

const input = "w-24 rounded-lg border border-slate-300 px-2 py-1 text-sm tabular-nums";

function Field({ label: text, help, children }: { label: string; help?: string; children: ReactNode }) {
  return (
    <label className="flex items-start justify-between gap-4 border-b border-slate-100 py-2.5 last:border-0">
      <span className="min-w-0">
        <span className="block text-sm text-slate-800">{text}</span>
        {help && <span className="block text-xs text-slate-500">{help}</span>}
      </span>
      <span className="shrink-0">{children}</span>
    </label>
  );
}

function NumberInput({ value, onChange, min, max, step = 1, suffix }: {
  value: number; onChange: (n: number) => void; min?: number; max?: number; step?: number; suffix?: string;
}) {
  return (
    <span className="flex items-center gap-1">
      <input type="number" className={input} value={Number.isFinite(value) ? value : ""} min={min} max={max} step={step}
        onChange={(e) => onChange(e.target.value === "" ? NaN : Number(e.target.value))} />
      {suffix && <span className="text-xs text-slate-500">{suffix}</span>}
    </span>
  );
}

/** Completion thresholds are stored 0–1 but edited as percentages. */
function PercentInput({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return <NumberInput value={Math.round(value * 100)} onChange={(n) => onChange(n / 100)} min={0} max={100} step={5} suffix="%" />;
}

function Card({ title, blurb, children }: { title: string; blurb?: string; children: ReactNode }) {
  return (
    <section className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
      <h3 className="font-semibold text-slate-900">{title}</h3>
      {blurb && <p className="text-xs text-slate-500">{blurb}</p>}
      <div className="mt-2">{children}</div>
    </section>
  );
}

export default function ConfigPage() {
  const [tab, setTab] = useState<"edit" | "history">("edit");
  const [active, setActive] = useState<ActiveConfig | null>(null);
  const [versions, setVersions] = useState<VersionSummary[]>([]);
  const [draft, setDraft] = useState<{ thresholds: Thresholds; prompt: string } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const vs = await clinicianApi.versions(); // seeds v1 on first use
      const a = await clinicianApi.activeConfig();
      setVersions(vs); setActive(a);
      setDraft({ thresholds: clone(a.thresholds), prompt: a.prompt_instructions });
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Could not load the model config.");
    }
  }, []);
  useEffect(() => { void reload(); }, [reload]);

  if (loadError) return <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{loadError}</p>;
  if (!active || !draft) return <p className="text-sm text-slate-500">Loading config…</p>;

  return (
    <>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Model config</h2>
          <p className="text-sm text-slate-500">
            Active: <span className="font-medium text-slate-800">v{active.version}</span>. New intakes, plans and reevaluations use it
            immediately; existing records keep the version that produced them.
          </p>
        </div>
        <div role="tablist" className="flex rounded-lg bg-slate-100 p-0.5">
          {(["edit", "history"] as const).map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
              className={`rounded-md px-3 py-1 text-sm ${tab === t ? "bg-white font-medium shadow-sm" : "text-slate-600"}`}>
              {t === "edit" ? "Edit" : `History (${versions.length})`}
            </button>
          ))}
        </div>
      </div>
      {tab === "edit"
        ? <Editor active={active} draft={draft} setDraft={setDraft} onSaved={async () => { await reload(); }} />
        : <History versions={versions} active={active}
            onActivated={reload}
            onLoad={async (v) => {
              const full = await clinicianApi.version(v);
              setDraft({ thresholds: clone(full.thresholds), prompt: full.prompt_instructions });
              setTab("edit");
            }} />}
    </>
  );
}

function Editor({ active, draft, setDraft, onSaved }: {
  active: ActiveConfig; draft: { thresholds: Thresholds; prompt: string };
  setDraft: (d: { thresholds: Thresholds; prompt: string }) => void; onSaved: () => Promise<void>;
}) {
  const t = draft.thresholds;
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [saved, setSaved] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<{ prompt: string; errors: string[] } | null>(null);

  const update = (fn: (t: Thresholds) => void) => {
    const next = clone(t);
    fn(next);
    setDraft({ ...draft, thresholds: next });
    setSaved(null);
  };
  const setReeval = (k: keyof Reeval) => (n: number) => update((x) => { x.reevaluation[k] = n; });
  const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  const diff = useMemo(() => changes(active.thresholds, t), [active, t]);
  const promptChanged = draft.prompt.trim() !== active.prompt_instructions.trim();
  const dirty = diff.length > 0 || promptChanged;

  async function save(activate: boolean) {
    setBusy(true); setErrors([]); setSaved(null);
    try {
      const v = await clinicianApi.saveVersion({ thresholds: t, prompt_instructions: draft.prompt, note, activate });
      setNote("");
      setSaved(activate ? `Saved and activated v${v.version}.` : `Saved v${v.version} as a draft (not active).`);
      await onSaved();
    } catch (e) {
      setErrors(errorList(e));
    } finally {
      setBusy(false);
    }
  }

  async function runPreview() {
    try { setPreview(await clinicianApi.preview(draft.prompt, t)); }
    catch (e) { setPreview({ prompt: "", errors: errorList(e) }); }
  }

  return (
    <div className="space-y-4 pb-40">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Intake scope" blurb="Who gets a plan and who is sent to a licensed therapist.">
          <Field label="Highest starting pain allowed" help="Intakes above this are referred out">
            <NumberInput value={t.scope.max_starting_pain} min={0} max={10}
              onChange={(n) => update((x) => { x.scope.max_starting_pain = n; })} suffix="/ 10" />
          </Field>
          <fieldset className="border-b border-slate-100 py-2.5">
            <legend className="text-sm text-slate-800">Regions we plan for</legend>
            <div className="mt-1 flex flex-wrap gap-3">
              {SUPPORTED_REGIONS.map((r) => (
                <label key={r} className="flex items-center gap-1.5 text-sm">
                  <input type="checkbox" checked={t.scope.supported_regions.includes(r)}
                    onChange={() => update((x) => { x.scope.supported_regions = toggle(x.scope.supported_regions, r); })} />
                  {label(r)}
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset className="py-2.5">
            <legend className="text-sm text-slate-800">Red flags that force a referral</legend>
            <div className="mt-1 flex flex-wrap gap-3">
              {RED_FLAGS.map((f) => (
                <label key={f} className="flex items-center gap-1.5 text-sm">
                  <input type="checkbox" checked={t.scope.red_flags.includes(f)}
                    onChange={() => update((x) => { x.scope.red_flags = toggle(x.scope.red_flags, f); })} />
                  {label(f)}
                </label>
              ))}
            </div>
          </fieldset>
        </Card>

        <Card title="Starting difficulty bands" blurb={`Every pain level from 0 to ${t.scope.max_starting_pain} needs exactly one band.`}>
          <table className="w-full text-sm">
            <thead className="text-xs text-slate-500">
              <tr><th className="py-1 text-left font-medium">Pain from</th><th className="text-left font-medium">to</th><th className="text-left font-medium">Level</th><th /></tr>
            </thead>
            <tbody>
              {t.difficulty_by_pain.map((b, i) => (
                <tr key={i}>
                  <td className="py-1"><NumberInput value={b.min_pain} min={0} max={10} onChange={(n) => update((x) => { x.difficulty_by_pain[i].min_pain = n; })} /></td>
                  <td><NumberInput value={b.max_pain} min={0} max={10} onChange={(n) => update((x) => { x.difficulty_by_pain[i].max_pain = n; })} /></td>
                  <td>
                    <select className="rounded-lg border border-slate-300 px-2 py-1 text-sm" value={b.level}
                      onChange={(e) => update((x) => { x.difficulty_by_pain[i].level = Number(e.target.value); })}>
                      {[1, 2, 3].map((l) => <option key={l} value={l}>Level {l}</option>)}
                    </select>
                  </td>
                  <td className="text-right">
                    <button type="button" className="text-xs text-slate-500 hover:text-red-700"
                      onClick={() => update((x) => { x.difficulty_by_pain.splice(i, 1); })}>Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button type="button" className="mt-2 text-sm text-teal-800 hover:underline"
            onClick={() => update((x) => { x.difficulty_by_pain.push({ min_pain: 0, max_pain: 0, level: 1 }); })}>+ Add band</button>
          <Field label="Exercise difficulty match" help="Exact level only, or that level and easier">
            <select className="rounded-lg border border-slate-300 px-2 py-1 text-sm" value={t.filtering.difficulty_match}
              onChange={(e) => update((x) => { x.filtering.difficulty_match = e.target.value as "exact" | "at_most"; })}>
              <option value="exact">Exact level</option>
              <option value="at_most">Level or easier</option>
            </select>
          </Field>
        </Card>

        <Card title="Plan shape">
          <Field label="Fewest exercises per plan"><NumberInput value={t.plan.min_exercises} min={1} max={12} onChange={(n) => update((x) => { x.plan.min_exercises = n; })} /></Field>
          <Field label="Most exercises per plan"><NumberInput value={t.plan.max_exercises} min={1} max={12} onChange={(n) => update((x) => { x.plan.max_exercises = n; })} /></Field>
          <Field label="Sessions per week"><NumberInput value={t.plan.default_frequency_per_week} min={1} max={7} onChange={(n) => update((x) => { x.plan.default_frequency_per_week = n; })} /></Field>
        </Card>

        <Card title="AI guardrails" blurb="The AI request timeout is set by LLM_TIMEOUT_S in .env, not here.">
          <Field label="Largest difficulty change the AI may suggest"><NumberInput value={t.ai.max_difficulty_change} min={0} max={2} suffix="levels" onChange={(n) => update((x) => { x.ai.max_difficulty_change = n; })} /></Field>
        </Card>
      </div>

      <Card title="Reevaluation rules" blurb="Checked in priority order: refer, then reduce, then increase, then reassess, else continue.">
        <div className="grid gap-x-8 lg:grid-cols-2">
          <div>
            <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">1 · Refer to a therapist</p>
            <Field label="Any session pain at or above"><NumberInput value={t.reevaluation.referral_session_pain} min={1} max={10} suffix="/ 10" onChange={setReeval("referral_session_pain")} /></Field>
            <Field label="Weekly average pain rises by" help="Across two weeks"><NumberInput value={t.reevaluation.referral_avg_pain_rise_two_weeks} step={0.5} min={0} suffix="pts" onChange={setReeval("referral_avg_pain_rise_two_weeks")} /></Field>
            <Field label="No improvement on intake pain after"><NumberInput value={t.reevaluation.referral_no_improvement_weeks} min={1} suffix="weeks" onChange={setReeval("referral_no_improvement_weeks")} /></Field>
            <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">2 · Reduce difficulty or frequency</p>
            <Field label="Weekly average pain rises by" help="In one week"><NumberInput value={t.reevaluation.reduce_avg_pain_rise_one_week} step={0.5} min={0} suffix="pts" onChange={setReeval("reduce_avg_pain_rise_one_week")} /></Field>
            <Field label="Completion below"><PercentInput value={t.reevaluation.reduce_completion_below} onChange={setReeval("reduce_completion_below")} /></Field>
          </div>
          <div>
            <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">3 · Increase difficulty one level</p>
            <Field label="Completion at least"><PercentInput value={t.reevaluation.increase_completion_at_least} onChange={setReeval("increase_completion_at_least")} /></Field>
            <Field label="With stable pain for"><NumberInput value={t.reevaluation.increase_stable_weeks} min={1} suffix="weeks" onChange={setReeval("increase_stable_weeks")} /></Field>
            <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">4 · Request a new assessment</p>
            <Field label="After"><NumberInput value={t.reevaluation.reassess_after_weeks} min={1} suffix="weeks" onChange={setReeval("reassess_after_weeks")} /></Field>
          </div>
        </div>
      </Card>

      <Card title="AI prompt" blurb="Your instructions come first. The rules block and patient data are added automatically and can't be edited.">
        <textarea value={draft.prompt} rows={7} maxLength={4000}
          onChange={(e) => { setDraft({ ...draft, prompt: e.target.value }); setSaved(null); }}
          className="mt-1 w-full rounded-lg border border-slate-300 p-3 font-mono text-sm" />
        <div className="mt-1 flex items-center justify-between text-xs text-slate-500">
          <span>{draft.prompt.length} / 4000</span>
          <button type="button" onClick={() => void runPreview()} className="text-sm text-teal-800 hover:underline">Preview full prompt</button>
        </div>
        <p className="mt-3 text-xs font-medium text-slate-500">Locked rules (from the current plan settings)</p>
        <pre className="mt-1 whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
{`Rules (always enforced):
- Choose between ${t.plan.min_exercises} and ${t.plan.max_exercises} exercises from the ELIGIBLE list below.
- Use only exercise ids that appear in ELIGIBLE; never invent ids or repeat one.
- For each exercise, sets must be within its [min, max] 'sets' range and reps within its [min, max] 'reps' range.`}
        </pre>
        {preview && (
          <div className="mt-3">
            {preview.errors.length > 0 && <ErrorList errors={preview.errors} />}
            <p className="text-xs font-medium text-slate-500">Full prompt with sample data</p>
            <pre className="mt-1 max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-900 p-3 text-xs text-slate-100">{preview.prompt}</pre>
          </div>
        )}
      </Card>

      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto max-w-6xl px-4 py-3">
          {errors.length > 0 && <ErrorList errors={errors} />}
          {saved && <p role="status" className="mb-2 text-sm text-teal-800">{saved}</p>}
          <p className="mb-2 truncate text-sm text-slate-600">
            {dirty ? <>{diff.length} setting{diff.length === 1 ? "" : "s"} changed{promptChanged ? " + prompt" : ""}
              <span className="hidden sm:inline">{diff.length > 0 && `: ${diff.slice(0, 3).map((c) => `${c.path} ${show(c.before)} → ${show(c.after)}`).join("; ")}${diff.length > 3 ? "…" : ""}`}</span></>
              : "No changes from the active version"}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <input aria-label="Change note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500}
              placeholder="Why are you making this change? (required)"
              className="min-w-[16rem] flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm" />
            <button type="button" disabled={busy} className="text-sm text-slate-600 hover:underline"
              onClick={() => { setDraft({ thresholds: clone(active.thresholds), prompt: active.prompt_instructions }); setErrors([]); }}>
              Discard
            </button>
            <button type="button" disabled={busy} className="text-sm text-slate-600 hover:underline"
              onClick={async () => { const d = await clinicianApi.defaults(); setDraft({ thresholds: d.thresholds, prompt: d.prompt_instructions }); }}>
              Load defaults
            </button>
            <button type="button" disabled={busy || !dirty} onClick={() => void save(false)}
              className="rounded-lg px-3 py-1.5 text-sm ring-1 ring-slate-300 hover:bg-slate-50 disabled:opacity-40">
              Save draft
            </button>
            <button type="button" disabled={busy || !dirty} onClick={() => void save(true)}
              className="rounded-lg bg-teal-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-800 disabled:opacity-40">
              Save and activate
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ErrorList({ errors }: { errors: string[] }) {
  return (
    <ul role="alert" className="mb-2 list-inside list-disc rounded-lg bg-red-50 p-2 text-sm text-red-800">
      {errors.map((e) => <li key={e}>{e}</li>)}
    </ul>
  );
}

function History({ versions, active, onActivated, onLoad }: {
  versions: VersionSummary[]; active: ActiveConfig; onActivated: () => Promise<void>; onLoad: (v: number) => Promise<void>;
}) {
  const [selected, setSelected] = useState<number | null>(versions[0]?.version ?? null);
  const [compareTo, setCompareTo] = useState<number | null>(null);
  const [diff, setDiff] = useState<Diff | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sel = versions.find((v) => v.version === selected);
  const base = compareTo ?? sel?.parent_version ?? null;

  useEffect(() => {
    setDiff(null);
    if (selected === null || base === null || base === selected) return;
    clinicianApi.diff(base, selected).then(setDiff).catch((e) => setError(e instanceof Error ? e.message : "Diff failed"));
  }, [selected, base]);

  async function activate(v: number) {
    if (!window.confirm(`Make v${v} the active config? New intakes, plans and reevaluations will use it right away.`)) return;
    try { await clinicianApi.activate(v); await onActivated(); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not activate"); }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,22rem)_1fr]">
      <ol className="space-y-2">
        {versions.map((v) => (
          <li key={v.version}>
            <button type="button" onClick={() => { setSelected(v.version); setCompareTo(null); }}
              className={`w-full rounded-xl p-3 text-left ring-1 ${selected === v.version ? "bg-teal-50 ring-teal-300" : "bg-white ring-slate-200 hover:bg-slate-50"}`}>
              <span className="flex items-center justify-between">
                <span className="font-medium">v{v.version}</span>
                {v.is_active && <span className="rounded-full bg-teal-700 px-2 py-0.5 text-xs text-white">Active</span>}
              </span>
              <span className="mt-0.5 block text-sm text-slate-700">{v.note || "No note"}</span>
              <span className="mt-0.5 block text-xs text-slate-500">
                {new Date(v.created_at).toLocaleString()}{v.author ? ` · ${v.author}` : ""}{v.parent_version ? ` · from v${v.parent_version}` : ""}
              </span>
            </button>
          </li>
        ))}
      </ol>
      {sel && (
        <section className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-semibold">v{sel.version}</h3>
            <div className="flex gap-2">
              <button type="button" onClick={() => void onLoad(sel.version)}
                className="rounded-lg px-3 py-1.5 text-sm ring-1 ring-slate-300 hover:bg-slate-50">Load into editor</button>
              {!sel.is_active && (
                <button type="button" onClick={() => void activate(sel.version)}
                  className="rounded-lg bg-teal-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-800">
                  {sel.version < (active.version ?? 0) ? "Roll back to this version" : "Activate"}
                </button>
              )}
            </div>
          </div>
          <label className="mt-3 block text-xs text-slate-500">Compare with
            <select className="ml-2 rounded-lg border border-slate-300 px-2 py-1 text-sm" value={base ?? ""}
              onChange={(e) => setCompareTo(e.target.value ? Number(e.target.value) : null)}>
              <option value="">{sel.parent_version ? `Parent (v${sel.parent_version})` : "—"}</option>
              {versions.filter((v) => v.version !== sel.version).map((v) => <option key={v.version} value={v.version}>v{v.version}{v.is_active ? " (active)" : ""}</option>)}
            </select>
          </label>
          {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
          {base === null ? <p className="mt-4 text-sm text-slate-500">This is the first version; pick another to compare.</p>
            : !diff ? <p className="mt-4 text-sm text-slate-500">Loading diff…</p> : (
              <div className="mt-4 space-y-4">
                {diff.threshold_changes.length === 0 ? <p className="text-sm text-slate-500">No threshold changes vs v{diff.base}.</p> : (
                  <table className="w-full text-sm">
                    <thead className="text-xs text-slate-500"><tr>
                      <th className="border-b py-1 text-left font-medium">Setting</th>
                      <th className="border-b py-1 text-left font-medium">v{diff.base}</th>
                      <th className="border-b py-1 text-left font-medium">v{diff.target}</th>
                    </tr></thead>
                    <tbody>{diff.threshold_changes.map((c) => (
                      <tr key={c.path} className="border-b border-slate-100">
                        <td className="py-1.5 font-mono text-xs">{c.path}</td>
                        <td className="py-1.5 text-red-800">{show(c.before)}</td>
                        <td className="py-1.5 text-teal-800">{show(c.after)}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                )}
                {diff.prompt_changed ? (
                  <div className="grid gap-3 md:grid-cols-2">
                    <div><p className="text-xs font-medium text-slate-500">Prompt in v{diff.base}</p>
                      <pre className="mt-1 whitespace-pre-wrap rounded-lg bg-red-50 p-2 text-xs">{diff.base_prompt}</pre></div>
                    <div><p className="text-xs font-medium text-slate-500">Prompt in v{diff.target}</p>
                      <pre className="mt-1 whitespace-pre-wrap rounded-lg bg-teal-50 p-2 text-xs">{diff.target_prompt}</pre></div>
                  </div>
                ) : <p className="text-sm text-slate-500">Prompt unchanged.</p>}
              </div>
            )}
        </section>
      )}
    </div>
  );
}
