// Types and calls for /api/clinician. Mirrors backend/app/modules/clinician and model_config schemas.
import { request } from "../api";

export interface Filters {
  start?: string;
  end?: string;
  region?: string;
  level?: number;
  version?: number;
}

export interface Count { key: string; count: number }

export interface Overview {
  filters: Filters;
  patients: number;
  intakes: number;
  in_scope_rate: number | null;
  active_plans: number;
  avg_completion: number | null;
  avg_pain_drop: number | null;
  referral_rate: number | null;
  ai_calls: number;
  ai_fallback_rate: number | null;
}

export interface IntakeAnalytics {
  total: number;
  in_scope: number;
  out_of_scope: number;
  in_scope_rate: number | null;
  out_of_scope_reasons: Count[];
  region_mix: Count[];
  starting_level_mix: Count[];
  weekly: { week_start: string; intakes: number; out_of_scope: number }[];
}

export interface OutcomeAnalytics {
  plans: number;
  active_plans: number;
  plan_source_mix: Count[];
  avg_completion: number | null;
  avg_pain_drop: number | null;
  by_week: { week_index: number; n: number; avg_post_pain: number | null; avg_completion: number | null; avg_missed: number | null }[];
  by_region: { region: string; plans: number; avg_intake_pain: number | null; avg_latest_pain: number | null; avg_pain_drop: number | null }[];
}

export interface RuleAnalytics {
  decisions: number;
  action_counts: Count[];
  reason_counts: Count[];
  patients_evaluated: number;
  patients_referred: number;
  referral_rate: number | null;
  weekly: { week_start: string; counts: Record<string, number> }[];
}

export interface AIAnalytics {
  calls: number;
  valid: number;
  fallback: number;
  fallback_rate: number | null;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  error_counts: Count[];
  by_task: Count[];
  weekly: { week_start: string; calls: number; fallback: number }[];
}

export interface VersionMetrics {
  version: number | null;
  label: string;
  is_active: boolean;
  note: string;
  created_at: string | null;
  intakes: number;
  in_scope_rate: number | null;
  plans: number;
  ai_plan_share: number | null;
  avg_completion: number | null;
  avg_pain_drop: number | null;
  decisions: number;
  action_counts: Record<string, number>;
  referral_rate: number | null;
  ai_calls: number;
  ai_fallback_rate: number | null;
  ai_latency_p50_ms: number | null;
}

export interface PatientSummary {
  code: string;
  region: string | null;
  starting_level: number | null;
  intake_pain: number | null;
  in_scope: boolean | null;
  days_since_intake: number | null;
  plan_status: string | null;
  plan_level: number | null;
  plan_source: string | null;
  weeks_logged: number;
  latest_avg_post_pain: number | null;
  latest_completion: number | null;
  last_action: string | null;
}

export interface PatientDetail {
  code: string;
  assessments: { day: number | null; region: string; pain_level: number; in_scope: boolean; reasons: string[]; starting_level: number | null; limitations: string[]; activity_difficulties: string[]; red_flags: string[] }[];
  plans: { number: number; day_started: number | null; status: string; difficulty_level: number; frequency_per_week: number; source: string; items: { exercise_id: string; sets: number; reps: number }[] }[];
  progress: { plan_number: number; week_index: number; completion_rate: number; avg_post_pain: number | null; max_session_pain: number | null; pain_change: number | null; missed_sessions: number }[];
  sessions: { day: number | null; plan_number: number | null; completed: boolean; pain_before: number; pain_after: number; perceived_difficulty: number }[];
  decisions: { day: number | null; plan_number: number | null; action: string; reasons: string[] }[];
  ai_logs: { day: number | null; task: string; valid: boolean; used_fallback: boolean; errors: string[]; latency_ms: number | null }[];
}

// ---------- model config ----------

export interface Band { min_pain: number; max_pain: number; level: number }

export interface Thresholds {
  scope: { supported_regions: string[]; max_starting_pain: number; red_flags: string[] };
  difficulty_by_pain: Band[];
  filtering: { difficulty_match: "exact" | "at_most" };
  plan: { min_exercises: number; max_exercises: number; default_frequency_per_week: number };
  reevaluation: {
    referral_session_pain: number;
    referral_avg_pain_rise_two_weeks: number;
    referral_no_improvement_weeks: number;
    reduce_avg_pain_rise_one_week: number;
    reduce_completion_below: number;
    increase_completion_at_least: number;
    increase_stable_weeks: number;
    reassess_after_weeks: number;
  };
  ai: { timeout_seconds: number; max_difficulty_change: number };
}

export interface ActiveConfig {
  version: number | null;
  thresholds: Thresholds;
  prompt_instructions: string;
  locked_rules: string;
}

export interface VersionSummary {
  version: number;
  is_active: boolean;
  note: string;
  author: string | null;
  parent_version: number | null;
  created_at: string;
}

export interface VersionFull extends VersionSummary {
  thresholds: Thresholds;
  prompt_instructions: string;
}

export interface Diff {
  base: number;
  target: number;
  threshold_changes: { path: string; before: unknown; after: unknown }[];
  prompt_changed: boolean;
  base_prompt: string;
  target_prompt: string;
}

function qs(f: Filters): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) if (v !== undefined && v !== "" && v !== null) p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const clinicianApi = {
  overview: (f: Filters) => request<Overview>(`/clinician/overview${qs(f)}`),
  intake: (f: Filters) => request<IntakeAnalytics>(`/clinician/analytics/intake${qs(f)}`),
  outcomes: (f: Filters) => request<OutcomeAnalytics>(`/clinician/analytics/outcomes${qs(f)}`),
  rules: (f: Filters) => request<RuleAnalytics>(`/clinician/analytics/rules${qs(f)}`),
  ai: (f: Filters) => request<AIAnalytics>(`/clinician/analytics/ai${qs(f)}`),
  byVersion: (f: Filters) => request<VersionMetrics[]>(`/clinician/analytics/by-version${qs({ ...f, version: undefined })}`),
  patients: (f: Filters) => request<PatientSummary[]>(`/clinician/patients${qs(f)}`),
  patient: (code: string) => request<PatientDetail>(`/clinician/patients/${encodeURIComponent(code)}`),

  activeConfig: () => request<ActiveConfig>("/clinician/config/active"),
  defaults: () => request<ActiveConfig>("/clinician/config/defaults"),
  versions: () => request<VersionSummary[]>("/clinician/config/versions"),
  version: (v: number) => request<VersionFull>(`/clinician/config/versions/${v}`),
  saveVersion: (body: { thresholds: Thresholds; prompt_instructions: string; note: string; activate: boolean }) =>
    request<VersionFull>("/clinician/config/versions", { method: "POST", body: JSON.stringify(body) }),
  activate: (v: number) => request<VersionSummary>(`/clinician/config/versions/${v}/activate`, { method: "POST" }),
  diff: (base: number, target: number) => request<Diff>(`/clinician/config/diff?base=${base}&target=${target}`),
  preview: (prompt_instructions: string, thresholds?: Thresholds) =>
    request<{ prompt: string; errors: string[] }>("/clinician/config/preview-prompt", {
      method: "POST", body: JSON.stringify({ prompt_instructions, thresholds }),
    }),
};

// ---------- formatting ----------

export const pct = (x: number | null | undefined) => (x === null || x === undefined ? "—" : `${Math.round(x * 100)}%`);
export const num = (x: number | null | undefined, digits = 1) =>
  x === null || x === undefined ? "—" : Number(x.toFixed(digits)).toLocaleString();

/** Server errors on config save arrive as {errors: string[]}. */
export function errorList(err: unknown): string[] {
  const detail = (err as { detail?: unknown })?.detail;
  if (detail && typeof detail === "object" && Array.isArray((detail as { errors?: unknown }).errors)) {
    return (detail as { errors: string[] }).errors;
  }
  return [err instanceof Error ? err.message : "Something went wrong"];
}
