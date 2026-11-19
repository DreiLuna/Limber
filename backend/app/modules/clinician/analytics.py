"""Cohort analytics for the clinician dashboard.

Every query is limited to users with role "patient". Filters:
  - start / end: inclusive date range on when the record was created;
  - region / level: matched against the intake (assessment) the record belongs to, so a plan,
    progress week, decision, or AI call is counted under the intake that produced it.

Aggregation is done in Python over the filtered rows. That keeps SQLite (tests, dev) and
Postgres behaving the same and is fine at MVP scale; move to SQL GROUP BY if volumes grow.
"""
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ai.models import AIOutputLog
from app.modules.assessment.models import Assessment
from app.modules.clinician import schemas as s
from app.modules.clinician.anonymize import day_offset, pseudonym, reason_key
from app.modules.model_config.models import ModelConfigVersion
from app.modules.plans.models import RecoveryPlan
from app.modules.progress.models import ProgressRecord
from app.modules.reevaluation.models import ReevaluationDecision
from app.modules.sessions.models import ExerciseSession
from app.modules.users.models import User

REEVALUATION_ACTIONS = ("refer", "reduce", "increase", "reassess", "continue")


@dataclass(frozen=True)
class Filters:
    start: date | None = None
    end: date | None = None
    region: str | None = None
    level: int | None = None
    # When filter_version is set, only records produced by config_version_id (None = untagged).
    filter_version: bool = False
    config_version_id: int | None = None
    version: int | None = None  # the version number, echoed back

    def out(self) -> s.Filters:
        return s.Filters(
            start=self.start.isoformat() if self.start else None,
            end=self.end.isoformat() if self.end else None,
            region=self.region, level=self.level, version=self.version,
        )

    def in_range(self, when: datetime | date | None) -> bool:
        if when is None:
            return self.start is None and self.end is None
        d = when.date() if isinstance(when, datetime) else when
        return (self.start is None or d >= self.start) and (self.end is None or d <= self.end)

    def version_ok(self, config_version_id: int | None) -> bool:
        return not self.filter_version or config_version_id == self.config_version_id

    def matches(self, a: Assessment | None) -> bool:
        if self.region is None and self.level is None:
            return True
        if a is None:
            return False
        return (self.region is None or a.body_region == self.region) and (
            self.level is None or a.starting_difficulty == self.level
        )


# ---------- helpers ----------

def _mean(xs: Iterable[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    return round(statistics.fmean(vals), 3) if vals else None


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


def _percentile(xs: list[int], p: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 1)


def _week_start(when: datetime | date) -> str:
    d = when.date() if isinstance(when, datetime) else when
    return (d - timedelta(days=d.weekday())).isoformat()


def _counts(c: Counter) -> list[s.Count]:
    return [s.Count(key=str(k), count=v) for k, v in sorted(c.items(), key=lambda kv: (-kv[1], str(kv[0])))]


def _patient_ids(db: Session) -> set[int]:
    return set(db.scalars(select(User.id).where(User.role == "patient")))


def _assessments(db: Session) -> dict[int, Assessment]:
    return {a.id: a for a in db.scalars(
        select(Assessment).join(User, User.id == Assessment.user_id).where(User.role == "patient")
    )}


def _plans(db: Session) -> dict[int, RecoveryPlan]:
    return {p.id: p for p in db.scalars(
        select(RecoveryPlan).join(User, User.id == RecoveryPlan.user_id).where(User.role == "patient")
    )}


def _plan_assessment(plan: RecoveryPlan | None, assessments: dict[int, Assessment]) -> Assessment | None:
    return assessments.get(plan.assessment_id) if plan else None


# ---------- intake / funnel ----------

def intake_analytics(db: Session, f: Filters) -> s.IntakeAnalytics:
    rows = [a for a in _assessments(db).values()
            if f.in_range(a.created_at) and f.matches(a) and f.version_ok(a.config_version_id)]
    out_reasons: Counter = Counter()
    weekly: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for a in rows:
        w = weekly[_week_start(a.created_at)]
        w[0] += 1
        if not a.in_scope:
            w[1] += 1
            out_reasons.update(reason_key(r) for r in a.referral_reasons or [])
    in_scope = sum(1 for a in rows if a.in_scope)
    return s.IntakeAnalytics(
        filters=f.out(), total=len(rows), in_scope=in_scope, out_of_scope=len(rows) - in_scope,
        in_scope_rate=_rate(in_scope, len(rows)),
        out_of_scope_reasons=_counts(out_reasons),
        region_mix=_counts(Counter(a.body_region for a in rows)),
        starting_level_mix=_counts(Counter(a.starting_difficulty for a in rows if a.starting_difficulty)),
        weekly=[s.WeeklyIntake(week_start=k, intakes=v[0], out_of_scope=v[1]) for k, v in sorted(weekly.items())],
    )


# ---------- outcomes ----------

def outcome_analytics(db: Session, f: Filters) -> s.OutcomeAnalytics:
    assessments = _assessments(db)
    plans = {pid: p for pid, p in _plans(db).items()
             if f.in_range(p.created_at) and f.matches(_plan_assessment(p, assessments))
             and f.version_ok(p.config_version_id)}
    records = [r for r in db.scalars(select(ProgressRecord)) if r.plan_id in plans]

    by_week: dict[int, list[ProgressRecord]] = defaultdict(list)
    by_plan: dict[int, list[ProgressRecord]] = defaultdict(list)
    for r in records:
        by_week[r.week_index].append(r)
        by_plan[r.plan_id].append(r)

    # Pain drop per plan = intake pain minus the most recent week's average post-session pain.
    region_rows: dict[str, list[tuple[int, float | None]]] = defaultdict(list)
    drops: list[float] = []
    for pid, plan in plans.items():
        a = _plan_assessment(plan, assessments)
        if a is None:
            continue
        weeks = sorted(by_plan.get(pid, []), key=lambda r: r.week_index)
        latest = next((r.avg_post_pain for r in reversed(weeks) if r.avg_post_pain is not None), None)
        region_rows[a.body_region].append((a.pain_level, latest))
        if latest is not None:
            drops.append(a.pain_level - latest)

    return s.OutcomeAnalytics(
        filters=f.out(),
        plans=len(plans),
        active_plans=sum(1 for p in plans.values() if p.status == "active"),
        plan_source_mix=_counts(Counter(p.source for p in plans.values())),
        avg_completion=_mean(r.completion_rate for r in records),
        avg_pain_drop=_mean(drops),
        by_week=[
            s.OutcomeWeek(
                week_index=wk, n=len(rs),
                avg_post_pain=_mean(r.avg_post_pain for r in rs),
                avg_completion=_mean(r.completion_rate for r in rs),
                avg_missed=_mean(r.missed_sessions for r in rs),
            )
            for wk, rs in sorted(by_week.items())
        ],
        by_region=[
            s.RegionOutcome(
                region=region, plans=len(rows),
                avg_intake_pain=_mean(p for p, _ in rows),
                avg_latest_pain=_mean(latest for _, latest in rows),
                avg_pain_drop=_mean(p - latest for p, latest in rows if latest is not None),
            )
            for region, rows in sorted(region_rows.items())
        ],
    )


# ---------- reevaluation rule firing ----------

def rule_analytics(db: Session, f: Filters) -> s.RuleAnalytics:
    assessments, plans = _assessments(db), _plans(db)
    rows = [
        d for d in db.scalars(select(ReevaluationDecision))
        if d.plan_id in plans and f.in_range(d.created_at) and f.version_ok(d.config_version_id)
        and f.matches(_plan_assessment(plans[d.plan_id], assessments))
    ]
    weekly: dict[str, Counter] = defaultdict(Counter)
    for d in rows:
        weekly[_week_start(d.created_at)][d.action] += 1
    evaluated = {d.user_id for d in rows}
    referred = {d.user_id for d in rows if d.action == "refer"}
    actions = Counter({a: 0 for a in REEVALUATION_ACTIONS})
    actions.update(d.action for d in rows)
    return s.RuleAnalytics(
        filters=f.out(), decisions=len(rows),
        action_counts=_counts(actions),
        reason_counts=_counts(Counter(reason_key(r) for d in rows for r in d.reasons or [])),
        patients_evaluated=len(evaluated), patients_referred=len(referred),
        referral_rate=_rate(len(referred), len(evaluated)),
        weekly=[s.WeeklyActions(week_start=k, counts=dict(v)) for k, v in sorted(weekly.items())],
    )


# ---------- AI quality ----------

def _log_assessment(log: AIOutputLog, assessments: dict[int, Assessment]) -> Assessment | None:
    aid = (log.request or {}).get("assessment_id")
    return assessments.get(aid) if isinstance(aid, int) else None


def ai_analytics(db: Session, f: Filters) -> s.AIAnalytics:
    patients, assessments = _patient_ids(db), _assessments(db)
    rows = [
        log for log in db.scalars(select(AIOutputLog))
        if log.user_id in patients and f.in_range(log.created_at) and f.version_ok(log.config_version_id)
        and f.matches(_log_assessment(log, assessments))
    ]
    weekly: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for log in rows:
        w = weekly[_week_start(log.created_at)]
        w[0] += 1
        w[1] += int(log.used_fallback)
    latencies = [log.latency_ms for log in rows if log.latency_ms is not None]
    fallback = sum(1 for log in rows if log.used_fallback)
    return s.AIAnalytics(
        filters=f.out(), calls=len(rows),
        valid=sum(1 for log in rows if log.valid), fallback=fallback,
        fallback_rate=_rate(fallback, len(rows)),
        latency_p50_ms=_percentile(latencies, 0.5), latency_p95_ms=_percentile(latencies, 0.95),
        error_counts=_counts(Counter(reason_key(e) for log in rows for e in log.errors or [])),
        by_task=_counts(Counter(log.task for log in rows)),
        weekly=[s.WeeklyAI(week_start=k, calls=v[0], fallback=v[1]) for k, v in sorted(weekly.items())],
    )


# ---------- overview ----------

def overview(db: Session, f: Filters) -> s.Overview:
    intake, outcomes = intake_analytics(db, f), outcome_analytics(db, f)
    rules, ai = rule_analytics(db, f), ai_analytics(db, f)
    patients = {
        a.user_id for a in _assessments(db).values()
        if f.in_range(a.created_at) and f.matches(a) and f.version_ok(a.config_version_id)
    }
    return s.Overview(
        filters=f.out(), patients=len(patients), intakes=intake.total,
        in_scope_rate=intake.in_scope_rate, active_plans=outcomes.active_plans,
        avg_completion=outcomes.avg_completion, avg_pain_drop=outcomes.avg_pain_drop,
        referral_rate=rules.referral_rate, ai_calls=ai.calls, ai_fallback_rate=ai.fallback_rate,
    )


# ---------- by config version ----------

def by_version(db: Session, f: Filters) -> list[s.VersionMetrics]:
    """The same headline metrics split by the config version that produced each record,
    so a clinician can see what changed after editing thresholds or the prompt."""
    versions = list(db.scalars(select(ModelConfigVersion).order_by(ModelConfigVersion.version)))
    out: list[s.VersionMetrics] = []
    for row in [None, *versions]:
        vf = replace(f, filter_version=True, config_version_id=row.id if row else None,
                     version=row.version if row else None)
        intake, outcomes = intake_analytics(db, vf), outcome_analytics(db, vf)
        rules, ai = rule_analytics(db, vf), ai_analytics(db, vf)
        if row is None and not (intake.total or outcomes.plans or rules.decisions or ai.calls):
            continue  # nothing recorded before versioning
        ai_plans = next((c.count for c in outcomes.plan_source_mix if c.key == "ai"), 0)
        out.append(s.VersionMetrics(
            version=row.version if row else None,
            label=f"v{row.version}" if row else "before versioning",
            is_active=bool(row and row.is_active),
            note=row.note if row else "",
            created_at=row.created_at.isoformat() if row else None,
            intakes=intake.total, in_scope_rate=intake.in_scope_rate,
            plans=outcomes.plans, ai_plan_share=_rate(ai_plans, outcomes.plans),
            avg_completion=outcomes.avg_completion, avg_pain_drop=outcomes.avg_pain_drop,
            decisions=rules.decisions,
            action_counts={c.key: c.count for c in rules.action_counts},
            referral_rate=rules.referral_rate,
            ai_calls=ai.calls, ai_fallback_rate=ai.fallback_rate, ai_latency_p50_ms=ai.latency_p50_ms,
        ))
    return out


# ---------- patients ----------

def _by_user(rows: Iterable, key: str = "user_id") -> dict[int, list]:
    out: dict[int, list] = defaultdict(list)
    for r in rows:
        out[getattr(r, key)].append(r)
    return out


def list_patients(db: Session, f: Filters) -> list[s.PatientSummary]:
    """One row per patient, keyed by pseudonym. region/level match the patient's latest intake;
    start/end match when that intake happened."""
    assessments = _by_user(_assessments(db).values())
    plans = _by_user(_plans(db).values())
    progress = _by_user(db.scalars(select(ProgressRecord)))
    decisions = _by_user(db.scalars(select(ReevaluationDecision)))
    today = date.today()

    out: list[s.PatientSummary] = []
    for uid in _patient_ids(db):
        a_list = sorted(assessments.get(uid, []), key=lambda a: (a.created_at, a.id))
        latest = a_list[-1] if a_list else None
        if not f.matches(latest) or (latest and not f.in_range(latest.created_at)):
            continue
        if latest is None and (f.start or f.end):
            continue
        p_list = sorted(plans.get(uid, []), key=lambda p: (p.created_at, p.id))
        plan = next((p for p in reversed(p_list) if p.status == "active"), p_list[-1] if p_list else None)
        weeks = sorted(
            (r for r in progress.get(uid, []) if plan and r.plan_id == plan.id), key=lambda r: r.week_index
        )
        last_week = weeks[-1] if weeks else None
        d_list = sorted(decisions.get(uid, []), key=lambda d: (d.created_at, d.id))
        out.append(s.PatientSummary(
            code=pseudonym(uid),
            region=latest.body_region if latest else None,
            starting_level=latest.starting_difficulty if latest else None,
            intake_pain=latest.pain_level if latest else None,
            in_scope=latest.in_scope if latest else None,
            days_since_intake=day_offset(today, a_list[0].created_at) if a_list else None,
            plan_status=plan.status if plan else None,
            plan_level=plan.difficulty_level if plan else None,
            plan_source=plan.source if plan else None,
            weeks_logged=len(weeks),
            latest_avg_post_pain=last_week.avg_post_pain if last_week else None,
            latest_completion=last_week.completion_rate if last_week else None,
            last_action=d_list[-1].action if d_list else None,
        ))
    return sorted(out, key=lambda p: p.code)


def patient_detail(db: Session, user_id: int) -> s.PatientDetail:
    def mine(model):
        return list(db.scalars(select(model).where(model.user_id == user_id)))

    a_list = sorted(mine(Assessment), key=lambda a: (a.created_at, a.id))
    origin = a_list[0].created_at if a_list else None
    p_list = sorted(mine(RecoveryPlan), key=lambda p: (p.created_at, p.id))
    plan_no = {p.id: i for i, p in enumerate(p_list, start=1)}

    return s.PatientDetail(
        code=pseudonym(user_id),
        assessments=[
            s.AssessmentView(
                day=day_offset(a.created_at, origin), region=a.body_region, pain_level=a.pain_level,
                in_scope=a.in_scope, reasons=[reason_key(r) for r in a.referral_reasons or []],
                starting_level=a.starting_difficulty, limitations=list(a.limitations or []),
                activity_difficulties=list(a.activity_difficulties or []), red_flags=list(a.red_flags or []),
            )
            for a in a_list
        ],
        plans=[
            s.PlanView(
                number=plan_no[p.id], day_started=day_offset(p.start_date, origin), status=p.status,
                difficulty_level=p.difficulty_level, frequency_per_week=p.frequency_per_week, source=p.source,
                items=[s.PlanItemView(exercise_id=i.exercise_id, sets=i.sets, reps=i.reps) for i in p.items],
            )
            for p in p_list
        ],
        progress=[
            s.ProgressView(
                plan_number=plan_no.get(r.plan_id, 0), week_index=r.week_index,
                completion_rate=r.completion_rate, avg_post_pain=r.avg_post_pain,
                max_session_pain=r.max_session_pain, pain_change=r.pain_change,
                missed_sessions=r.missed_sessions,
            )
            for r in sorted(mine(ProgressRecord), key=lambda r: (plan_no.get(r.plan_id, 0), r.week_index))
        ],
        sessions=[
            s.SessionView(
                day=day_offset(x.performed_at, origin), plan_number=plan_no.get(x.plan_id),
                completed=x.completed, pain_before=x.pain_before, pain_after=x.pain_after,
                perceived_difficulty=x.perceived_difficulty,
            )
            for x in sorted(mine(ExerciseSession), key=lambda x: (x.performed_at, x.id))
        ],
        decisions=[
            s.DecisionView(
                day=day_offset(d.created_at, origin), plan_number=plan_no.get(d.plan_id),
                action=d.action, reasons=[reason_key(r) for r in d.reasons or []],
            )
            for d in sorted(mine(ReevaluationDecision), key=lambda d: (d.created_at, d.id))
        ],
        ai_logs=[
            s.AILogView(
                day=day_offset(log.created_at, origin), task=log.task, valid=log.valid,
                used_fallback=log.used_fallback, errors=[reason_key(e) for e in log.errors or []],
                latency_ms=log.latency_ms,
            )
            for log in sorted(mine(AIOutputLog), key=lambda log: (log.created_at, log.id))
        ],
    )
