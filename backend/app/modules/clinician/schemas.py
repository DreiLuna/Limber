"""Response shapes for /api/clinician. None of these carry ids, emails, names, dates of
individual events, or free text. See anonymize.py for the rules."""
from pydantic import BaseModel


class Filters(BaseModel):
    start: str | None = None  # ISO date, inclusive
    end: str | None = None    # ISO date, inclusive
    region: str | None = None
    level: int | None = None
    version: int | None = None


class Count(BaseModel):
    key: str
    count: int


class WeeklyIntake(BaseModel):
    week_start: str
    intakes: int
    out_of_scope: int


class IntakeAnalytics(BaseModel):
    filters: Filters
    total: int
    in_scope: int
    out_of_scope: int
    in_scope_rate: float | None
    out_of_scope_reasons: list[Count]
    region_mix: list[Count]
    starting_level_mix: list[Count]
    weekly: list[WeeklyIntake]


class OutcomeWeek(BaseModel):
    week_index: int
    n: int
    avg_post_pain: float | None
    avg_completion: float | None
    avg_missed: float | None


class RegionOutcome(BaseModel):
    region: str
    plans: int
    avg_intake_pain: float | None
    avg_latest_pain: float | None
    avg_pain_drop: float | None


class OutcomeAnalytics(BaseModel):
    filters: Filters
    plans: int
    active_plans: int
    plan_source_mix: list[Count]
    avg_completion: float | None
    avg_pain_drop: float | None
    by_week: list[OutcomeWeek]
    by_region: list[RegionOutcome]


class WeeklyActions(BaseModel):
    week_start: str
    counts: dict[str, int]


class RuleAnalytics(BaseModel):
    filters: Filters
    decisions: int
    action_counts: list[Count]
    reason_counts: list[Count]
    patients_evaluated: int
    patients_referred: int
    referral_rate: float | None
    weekly: list[WeeklyActions]


class WeeklyAI(BaseModel):
    week_start: str
    calls: int
    fallback: int


class AIAnalytics(BaseModel):
    filters: Filters
    calls: int
    valid: int
    fallback: int
    fallback_rate: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    error_counts: list[Count]
    by_task: list[Count]
    weekly: list[WeeklyAI]


class Overview(BaseModel):
    filters: Filters
    patients: int
    intakes: int
    in_scope_rate: float | None
    active_plans: int
    avg_completion: float | None
    avg_pain_drop: float | None
    referral_rate: float | None
    ai_calls: int
    ai_fallback_rate: float | None


class PatientSummary(BaseModel):
    code: str
    region: str | None
    starting_level: int | None
    intake_pain: int | None
    in_scope: bool | None
    days_since_intake: int | None
    plan_status: str | None
    plan_level: int | None
    plan_source: str | None
    weeks_logged: int
    latest_avg_post_pain: float | None
    latest_completion: float | None
    last_action: str | None


class AssessmentView(BaseModel):
    day: int | None
    region: str
    pain_level: int
    in_scope: bool
    reasons: list[str]
    starting_level: int | None
    limitations: list[str]
    activity_difficulties: list[str]
    red_flags: list[str]


class PlanItemView(BaseModel):
    exercise_id: str
    sets: int
    reps: int


class PlanView(BaseModel):
    number: int  # 1-based order for this patient, not a database id
    day_started: int | None
    status: str
    difficulty_level: int
    frequency_per_week: int
    source: str
    items: list[PlanItemView]


class ProgressView(BaseModel):
    plan_number: int
    week_index: int
    completion_rate: float
    avg_post_pain: float | None
    max_session_pain: int | None
    pain_change: float | None
    missed_sessions: int


class SessionView(BaseModel):
    day: int | None
    plan_number: int | None
    completed: bool
    pain_before: int
    pain_after: int
    perceived_difficulty: int


class DecisionView(BaseModel):
    day: int | None
    plan_number: int | None
    action: str
    reasons: list[str]


class AILogView(BaseModel):
    day: int | None
    task: str
    valid: bool
    used_fallback: bool
    errors: list[str]
    latency_ms: int | None


class PatientDetail(BaseModel):
    code: str
    assessments: list[AssessmentView]
    plans: list[PlanView]
    progress: list[ProgressView]
    sessions: list[SessionView]
    decisions: list[DecisionView]
    ai_logs: list[AILogView]


class VersionMetrics(BaseModel):
    version: int | None  # None = records made before config versioning existed
    label: str
    is_active: bool
    note: str
    created_at: str | None
    intakes: int
    in_scope_rate: float | None
    plans: int
    ai_plan_share: float | None
    avg_completion: float | None
    avg_pain_drop: float | None
    decisions: int
    action_counts: dict[str, int]
    referral_rate: float | None
    ai_calls: int
    ai_fallback_rate: float | None
    ai_latency_p50_ms: float | None
