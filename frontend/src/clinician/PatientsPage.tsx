import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { label } from "../types";
import { clinicianApi, num, pct, type PatientDetail, type PatientSummary } from "./api";
import { ChartCard, DataTable, Lines, SERIES } from "./charts";
import { FilterBar, useFilters } from "./FilterBar";
import { reasonLabel } from "./OverviewPage";

type SortKey = "code" | "days_since_intake" | "intake_pain" | "latest_avg_post_pain" | "latest_completion";

const STATUS_STYLE: Record<string, string> = {
  active: "bg-teal-50 text-teal-800 ring-teal-200",
  referred: "bg-red-50 text-red-800 ring-red-200",
  reassessment_required: "bg-amber-50 text-amber-800 ring-amber-200",
  superseded: "bg-slate-50 text-slate-600 ring-slate-200",
};

function Status({ value }: { value: string | null }) {
  if (!value) return <span className="text-slate-400">No plan</span>;
  return <span className={`rounded-full px-2 py-0.5 text-xs ring-1 ${STATUS_STYLE[value] ?? STATUS_STYLE.superseded}`}>{label(value)}</span>;
}

export default function PatientsPage() {
  const [filters, setFilters] = useFilters();
  const [rows, setRows] = useState<PatientSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "code", desc: false });

  useEffect(() => {
    let live = true;
    const { version: _ignored, ...rest } = filters; // the list is per patient, not per version
    clinicianApi.patients(rest).then((r) => live && setRows(r))
      .catch((e) => live && setError(e instanceof Error ? e.message : "Could not load patients."));
    return () => { live = false; };
  }, [filters]);

  const shown = useMemo(() => {
    const q = query.trim().toUpperCase();
    const list = (rows ?? []).filter((r) => !q || r.code.includes(q));
    return [...list].sort((a, b) => {
      const x = a[sort.key], y = b[sort.key];
      const cmp = x === y ? 0 : x === null ? 1 : y === null ? -1 : x < y ? -1 : 1;
      return sort.desc ? -cmp : cmp;
    });
  }, [rows, query, sort]);

  const th = (key: SortKey, text: string) => (
    <th className="border-b px-3 py-2 font-medium">
      <button type="button" className="hover:text-slate-900"
        onClick={() => setSort((s) => ({ key, desc: s.key === key ? !s.desc : false }))}>
        {text}{sort.key === key ? (sort.desc ? " ↓" : " ↑") : ""}
      </button>
    </th>
  );

  return (
    <>
      <FilterBar filters={filters} onChange={setFilters} showVersion={false} />
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-slate-500">
          Patients are shown by code only. Region and level match each patient's latest intake.
        </p>
        <input type="search" placeholder="Find code, e.g. P-7F3A" value={query} onChange={(e) => setQuery(e.target.value)}
          className="w-56 rounded-lg border border-slate-300 px-3 py-1.5 text-sm" />
      </div>
      {error && <p role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      <div className="overflow-x-auto rounded-xl bg-white ring-1 ring-slate-200">
        <table className="w-full min-w-[48rem] text-left text-sm">
          <thead className="text-xs text-slate-500">
            <tr>
              {th("code", "Patient")}
              <th className="border-b px-3 py-2 font-medium">Region</th>
              {th("intake_pain", "Intake pain")}
              {th("days_since_intake", "Days in program")}
              <th className="border-b px-3 py-2 font-medium">Plan</th>
              <th className="border-b px-3 py-2 font-medium">Weeks</th>
              {th("latest_avg_post_pain", "Latest pain")}
              {th("latest_completion", "Latest completion")}
              <th className="border-b px-3 py-2 font-medium">Last decision</th>
            </tr>
          </thead>
          <tbody>
            {rows === null ? <tr><td colSpan={9} className="px-3 py-6 text-center text-slate-500">Loading…</td></tr>
              : shown.length === 0 ? <tr><td colSpan={9} className="px-3 py-6 text-center text-slate-500">No patients match.</td></tr>
                : shown.map((p) => (
                  <tr key={p.code} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="px-3 py-2 font-mono">
                      <Link to={`/clinician/patients/${p.code}`} className="text-teal-800 hover:underline">{p.code}</Link>
                    </td>
                    <td className="px-3 py-2">{p.region ? label(p.region) : "—"}{p.starting_level ? ` · L${p.starting_level}` : ""}</td>
                    <td className="px-3 py-2 tabular-nums">{p.intake_pain ?? "—"}{p.in_scope === false && <span className="ml-1 text-xs text-red-700">out of scope</span>}</td>
                    <td className="px-3 py-2 tabular-nums">{p.days_since_intake ?? "—"}</td>
                    <td className="px-3 py-2"><Status value={p.plan_status} />{p.plan_source && <span className="ml-1 text-xs text-slate-500">{p.plan_source === "ai" ? "AI" : "rules"} · L{p.plan_level}</span>}</td>
                    <td className="px-3 py-2 tabular-nums">{p.weeks_logged}</td>
                    <td className="px-3 py-2 tabular-nums">{num(p.latest_avg_post_pain)}</td>
                    <td className="px-3 py-2 tabular-nums">{pct(p.latest_completion)}</td>
                    <td className="px-3 py-2">{p.last_action ? label(p.last_action) : "—"}</td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function PatientDetailPage() {
  const { code = "" } = useParams();
  const [d, setD] = useState<PatientDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    clinicianApi.patient(code).then((r) => live && setD(r))
      .catch((e) => live && setError(e instanceof Error ? e.message : "Could not load patient."));
    return () => { live = false; };
  }, [code]);

  if (error) return <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>;
  if (!d) return <p className="text-sm text-slate-500">Loading…</p>;

  const latest = d.assessments[d.assessments.length - 1];
  const pain = d.sessions.map((s) => ({ day: `Day ${s.day ?? "?"}`, before: s.pain_before, after: s.pain_after }));

  return (
    <div className="space-y-6">
      <div>
        <Link to="/clinician/patients" className="text-sm text-slate-500 hover:underline">← All patients</Link>
        <h2 className="mt-1 font-mono text-2xl font-semibold">{d.code}</h2>
        {latest && (
          <p className="text-sm text-slate-600">
            {label(latest.region)} · intake pain {latest.pain_level}
            {latest.starting_level ? ` · starting level ${latest.starting_level}` : ""}
            {latest.limitations.length > 0 && ` · limits: ${latest.limitations.map(label).join(", ")}`}
            {latest.activity_difficulties.length > 0 && ` · hard: ${latest.activity_difficulties.map(label).join(", ")}`}
          </p>
        )}
        <p className="text-xs text-slate-500">Days are counted from this patient's first intake.</p>
      </div>

      <ChartCard title="Session pain" subtitle="Reported before and after each session (0–10)" empty={!pain.length}
        table={{ columns: ["Day", "Before", "After"], rows: pain.map((p) => [p.day, p.before, p.after]) }}>
        <Lines data={pain} xKey="day" domain={[0, 10]}
          series={[{ key: "before", label: "Before session", color: SERIES[1] }, { key: "after", label: "After session", color: SERIES[0] }]} />
      </ChartCard>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Weekly progress" empty={!d.progress.length}>
          <DataTable columns={["Plan", "Week", "Completion", "Avg pain", "Max pain", "Change", "Missed"]}
            rows={d.progress.map((r) => [r.plan_number, r.week_index + 1, pct(r.completion_rate), num(r.avg_post_pain),
              r.max_session_pain ?? "—", num(r.pain_change), r.missed_sessions])} />
        </ChartCard>
        <ChartCard title="Reevaluation decisions" empty={!d.decisions.length}>
          <ol className="space-y-2 text-sm">
            {d.decisions.map((x, i) => (
              <li key={i} className="flex gap-3">
                <span className="w-14 shrink-0 tabular-nums text-slate-500">Day {x.day}</span>
                <span><span className="font-medium">{label(x.action)}</span>
                  {x.reasons.length > 0 && <span className="text-slate-600"> — {x.reasons.map(reasonLabel).join(", ")}</span>}</span>
              </li>
            ))}
          </ol>
        </ChartCard>
      </div>

      <ChartCard title="Plans" empty={!d.plans.length}>
        <div className="space-y-4">
          {d.plans.map((p) => (
            <div key={p.number}>
              <p className="mb-1 text-sm">
                <span className="font-medium">Plan {p.number}</span> · day {p.day_started} · <Status value={p.status} /> ·
                level {p.difficulty_level} · {p.frequency_per_week}×/week · {p.source === "ai" ? "AI" : "rule-based"}
              </p>
              <DataTable columns={["Exercise", "Sets", "Reps"]}
                rows={p.items.map((i) => [i.exercise_id.replace(/_/g, " "), i.sets, i.reps])} />
            </div>
          ))}
        </div>
      </ChartCard>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Intakes" empty={!d.assessments.length}>
          <DataTable columns={["Day", "Region", "Pain", "Result"]}
            rows={d.assessments.map((a) => [a.day ?? "—", label(a.region), a.pain_level,
              a.in_scope ? `In scope · L${a.starting_level}` : `Referred: ${a.reasons.map(reasonLabel).join(", ")}`])} />
        </ChartCard>
        <ChartCard title="AI calls" empty={!d.ai_logs.length}>
          <DataTable columns={["Day", "Task", "Result", "Latency"]}
            rows={d.ai_logs.map((l) => [l.day ?? "—", label(l.task),
              l.valid ? "Valid" : `Fallback${l.errors.length ? `: ${l.errors.map(reasonLabel).join(", ")}` : ""}`,
              l.latency_ms === null ? "—" : `${l.latency_ms} ms`])} />
        </ChartCard>
      </div>
    </div>
  );
}
