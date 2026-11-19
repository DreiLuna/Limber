import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { label } from "../types";
import {
  clinicianApi, num, pct,
  type AIAnalytics, type IntakeAnalytics, type OutcomeAnalytics, type Overview, type RuleAnalytics, type VersionMetrics,
} from "./api";
import { BarList, ChartCard, DataTable, Lines, SERIES, StackedColumns, StatTile, weekLabel, type Series } from "./charts";
import { FilterBar, useFilters } from "./FilterBar";

// Each reevaluation action keeps the same colour everywhere (colour follows the entity).
export const ACTIONS = ["refer", "reduce", "increase", "reassess", "continue"] as const;
export const ACTION_SERIES: Series[] = ACTIONS.map((a, i) => ({ key: a, label: label(a), color: SERIES[i] }));

const REASON_COPY: Record<string, string> = {
  pain_too_high: "Starting pain too high",
  red_flag_reported: "Red flag reported in session",
  session_pain: "Session pain at referral level",
  avg_pain_rose_over_two_weeks: "Pain rose over two weeks",
  avg_pain_rose_in_one_week: "Pain rose in one week",
  no_improvement_after_weeks: "No improvement",
  completion: "Completion threshold",
  plan_complete_after_weeks: "Plan finished, reassess",
  not_eligible: "Exercise not in eligible list",
  sets_out_of_range: "Sets out of range",
  reps_out_of_range: "Reps out of range",
  count: "Wrong number of exercises",
  schema: "Malformed JSON",
};
export const reasonLabel = (k: string) => {
  if (REASON_COPY[k]) return REASON_COPY[k];
  const [head, tail] = k.split(":");
  if (tail) return `${label(head)}: ${label(tail)}`;
  return label(k);
};

interface Data {
  overview: Overview; intake: IntakeAnalytics; outcomes: OutcomeAnalytics;
  rules: RuleAnalytics; ai: AIAnalytics; versions: VersionMetrics[];
}

export default function OverviewPage() {
  const [filters, setFilters] = useFilters();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setError(null);
    Promise.all([
      clinicianApi.overview(filters), clinicianApi.intake(filters), clinicianApi.outcomes(filters),
      clinicianApi.rules(filters), clinicianApi.ai(filters), clinicianApi.byVersion(filters),
    ]).then(([overview, intake, outcomes, rules, ai, versions]) => {
      if (live) setData({ overview, intake, outcomes, rules, ai, versions });
    }).catch((e) => live && setError(e instanceof Error ? e.message : "Could not load analytics."));
    return () => { live = false; };
  }, [filters]);

  return (
    <>
      <FilterBar filters={filters} onChange={setFilters} />
      {error && <p role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {!data ? <p className="text-sm text-slate-500">Loading analytics…</p> : <Sections d={data} />}
    </>
  );
}

function Sections({ d }: { d: Data }) {
  const o = d.overview;
  return (
    <div className="space-y-10">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Patients" value={o.patients.toLocaleString()} hint={`${o.intakes} intakes`} />
        <StatTile label="In-scope rate" value={pct(o.in_scope_rate)} hint="Intakes that got a plan" />
        <StatTile label="Active plans" value={o.active_plans.toLocaleString()} />
        <StatTile label="Avg completion" value={pct(o.avg_completion)} hint="Per plan week" />
        <StatTile label="Avg pain drop" value={o.avg_pain_drop === null ? "—" : `${num(o.avg_pain_drop)} pts`}
          hint="Intake pain minus latest week" />
        <StatTile label="Referral rate" value={pct(o.referral_rate)} hint="Of reevaluated patients" />
        <StatTile label="AI plan calls" value={o.ai_calls.toLocaleString()} />
        <StatTile label="AI fallback rate" value={pct(o.ai_fallback_rate)} hint="Rule-based plan used instead" />
      </div>

      <IntakeSection a={d.intake} />
      <OutcomeSection a={d.outcomes} />
      <RuleSection a={d.rules} />
      <AISection a={d.ai} />
      <VersionSection rows={d.versions} />
    </div>
  );
}

function Section({ title, blurb, children }: { title: string; blurb: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      <p className="mb-3 text-sm text-slate-500">{blurb}</p>
      <div className="grid gap-4 lg:grid-cols-2">{children}</div>
    </section>
  );
}

function IntakeSection({ a }: { a: IntakeAnalytics }) {
  const weekly = a.weekly.map((w) => ({ ...w, in_scope: w.intakes - w.out_of_scope }));
  return (
    <Section title="Intake and scope" blurb={`${a.total} intakes · ${a.out_of_scope} routed to a therapist`}>
      <ChartCard title="Intakes per week" subtitle="Split by the scope check result" empty={!weekly.length}
        table={{ columns: ["Week of", "In scope", "Out of scope"], rows: weekly.map((w) => [w.week_start, w.in_scope, w.out_of_scope]) }}>
        <StackedColumns data={weekly} xKey="week_start" xFormat={weekLabel}
          series={[{ key: "in_scope", label: "In scope", color: SERIES[0] }, { key: "out_of_scope", label: "Out of scope", color: SERIES[1] }]} />
      </ChartCard>
      <ChartCard title="Why intakes were out of scope" subtitle="A single intake can have several reasons"
        empty={!a.out_of_scope_reasons.length}>
        <BarList items={a.out_of_scope_reasons} labelOf={reasonLabel} color={SERIES[1]} />
      </ChartCard>
      <ChartCard title="Body region mix" empty={!a.region_mix.length}>
        <BarList items={a.region_mix} labelOf={label} />
      </ChartCard>
      <ChartCard title="Starting difficulty" subtitle="Set from intake pain by the pain bands" empty={!a.starting_level_mix.length}>
        <BarList items={[...a.starting_level_mix].sort((x, y) => x.key.localeCompare(y.key))} labelOf={(k) => `Level ${k}`} />
      </ChartCard>
    </Section>
  );
}

function OutcomeSection({ a }: { a: OutcomeAnalytics }) {
  const weeks = a.by_week.map((w) => ({ ...w, week: `Week ${w.week_index + 1}` }));
  return (
    <Section title="Recovery outcomes" blurb={`${a.plans} plans · ${a.active_plans} active`}>
      <ChartCard title="Average post-session pain by plan week" subtitle="0–10 scale, lower is better" empty={!weeks.length}
        table={{ columns: ["Week", "Patients", "Avg pain", "Completion", "Missed"],
          rows: weeks.map((w) => [w.week, w.n, num(w.avg_post_pain), pct(w.avg_completion), num(w.avg_missed)]) }}>
        <Lines data={weeks} xKey="week" domain={[0, 10]} yFormat={(v) => num(v)}
          series={[{ key: "avg_post_pain", label: "Avg post-session pain", color: SERIES[0] }]} />
      </ChartCard>
      <ChartCard title="Session completion by plan week" subtitle="Share of scheduled sessions completed" empty={!weeks.length}
        table={{ columns: ["Week", "Completion"], rows: weeks.map((w) => [w.week, pct(w.avg_completion)]) }}>
        <Lines data={weeks} xKey="week" domain={[0, 1]} yFormat={(v) => pct(v)}
          series={[{ key: "avg_completion", label: "Completion", color: SERIES[2] }]} />
      </ChartCard>
      <ChartCard title="Pain change by region" empty={!a.by_region.length}>
        <DataTable columns={["Region", "Plans", "Intake pain", "Latest pain", "Drop"]}
          rows={a.by_region.map((r) => [label(r.region), r.plans, num(r.avg_intake_pain), num(r.avg_latest_pain), num(r.avg_pain_drop)])} />
      </ChartCard>
      <ChartCard title="Plan source" subtitle="AI-personalized vs rule-based fallback" empty={!a.plan_source_mix.length}>
        <BarList items={a.plan_source_mix} labelOf={(k) => (k === "ai" ? "AI" : label(k))} />
      </ChartCard>
    </Section>
  );
}

function RuleSection({ a }: { a: RuleAnalytics }) {
  const weekly = a.weekly.map((w) => ({ week_start: w.week_start, ...Object.fromEntries(ACTIONS.map((x) => [x, w.counts[x] ?? 0])) }));
  const byAction = ACTIONS.map((x) => ({ key: x, count: a.action_counts.find((c) => c.key === x)?.count ?? 0 }));
  return (
    <Section title="Reevaluation rules"
      blurb={`${a.decisions} decisions · ${a.patients_referred} of ${a.patients_evaluated} reevaluated patients referred (${pct(a.referral_rate)})`}>
      <ChartCard title="Decisions per week" subtitle="Which rule fired at each reevaluation" empty={!weekly.length}
        table={{ columns: ["Week of", ...ACTIONS.map(label)], rows: weekly.map((w) => [w.week_start, ...ACTIONS.map((x) => (w as Record<string, number | string>)[x])]) }}>
        <StackedColumns data={weekly} xKey="week_start" xFormat={weekLabel} series={ACTION_SERIES} />
      </ChartCard>
      <ChartCard title="Decisions by action" empty={!a.decisions}>
        <BarList items={byAction} labelOf={label} />
      </ChartCard>
      <ChartCard title="Reasons behind decisions" subtitle="Values stripped; grouped by rule" empty={!a.reason_counts.length}>
        <BarList items={a.reason_counts} labelOf={reasonLabel} />
      </ChartCard>
    </Section>
  );
}

function AISection({ a }: { a: AIAnalytics }) {
  const weekly = a.weekly.map((w) => ({ week_start: w.week_start, valid: w.calls - w.fallback, fallback: w.fallback }));
  return (
    <Section title="AI planner quality"
      blurb={`${a.calls} calls · ${pct(a.fallback_rate)} fell back · median ${num(a.latency_p50_ms, 0)} ms, p95 ${num(a.latency_p95_ms, 0)} ms`}>
      <ChartCard title="AI calls per week" subtitle="Valid AI output vs rule-based fallback" empty={!weekly.length}
        table={{ columns: ["Week of", "Valid", "Fallback"], rows: weekly.map((w) => [w.week_start, w.valid, w.fallback]) }}>
        <StackedColumns data={weekly} xKey="week_start" xFormat={weekLabel}
          series={[{ key: "valid", label: "Valid AI plan", color: SERIES[0] }, { key: "fallback", label: "Fell back", color: SERIES[1] }]} />
      </ChartCard>
      <ChartCard title="Validation errors" subtitle="Why AI output was rejected" empty={!a.error_counts.length}>
        <BarList items={a.error_counts} labelOf={reasonLabel} color={SERIES[1]} />
      </ChartCard>
    </Section>
  );
}

function VersionSection({ rows }: { rows: VersionMetrics[] }) {
  return (
    <section>
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-slate-900">By config version</h2>
        <Link to="/clinician/config" className="text-sm text-teal-800 hover:underline">Edit model config</Link>
      </div>
      <p className="mb-3 text-sm text-slate-500">Each record is counted under the thresholds and prompt that produced it.</p>
      <div className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
        {rows.length === 0 ? <p className="py-6 text-center text-sm text-slate-500">No versions yet.</p> : (
          <DataTable
            columns={["Version", "Note", "Intakes", "In scope", "Plans", "AI plans", "Completion", "Pain drop", "Referral", "AI fallback"]}
            rows={rows.map((v) => [
              `${v.label}${v.is_active ? " · active" : ""}`, v.note || "—", v.intakes, pct(v.in_scope_rate), v.plans,
              pct(v.ai_plan_share), pct(v.avg_completion), num(v.avg_pain_drop), pct(v.referral_rate), pct(v.ai_fallback_rate),
            ])} />
        )}
      </div>
    </section>
  );
}
