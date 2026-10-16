"""Apply deterministic reevaluation inside the caller's transaction, without an LLM."""
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_thresholds
from app.core.database import utcnow
from app.core.vocab import ReevaluationAction as Action
from app.modules.assessment.models import Assessment
from app.modules.assessment.scope import check_scope
from app.modules.catalog.models import Exercise
from app.modules.notifications.models import Notification
from app.modules.plans.models import PlanItem, RecoveryPlan, ScheduledSession
from app.modules.plans.scheduling import build_schedule
from app.modules.progress.metrics import WeekStats
from app.modules.recommendation.filtering import InsufficientExercisesError, build_fallback_plan, filter_exercises
from app.modules.reevaluation.models import ReevaluationDecision
from app.modules.reevaluation.rules import Decision, ReevaluationInput, evaluate
from app.modules.sessions.models import ExerciseSession, PainReport


def completed_week_stats(db: Session, plan: RecoveryPlan, today: date) -> list[WeekStats]:
    """Full seven-day plan weeks only; extra logs affect pain, not adherence."""
    finished = max(0, (today - plan.start_date).days // 7)
    schedule = list(db.scalars(select(ScheduledSession).where(ScheduledSession.plan_id == plan.id)))
    scheduled = {item.id: item for item in schedule}
    logs = list(db.scalars(select(ExerciseSession).where(
        ExerciseSession.plan_id == plan.id, ExerciseSession.user_id == plan.user_id,
    )))
    stats, previous = [], None
    for week in range(finished):
        dates = {item.id for item in schedule if item.week_index == week}
        entries = [item for item in logs if (
            scheduled[item.scheduled_session_id].week_index if item.scheduled_session_id in scheduled
            else (item.performed_at.date() - plan.start_date).days // 7
        ) == week]
        completed = {item.scheduled_session_id for item in entries if item.completed} & dates
        pains = [item.pain_after for item in entries if item.completed]
        avg = round(sum(pains) / len(pains), 2) if pains else None
        stats.append(WeekStats(
            week, len(completed) / len(dates) if dates else 0.0, avg,
            max((max(item.pain_before, item.pain_after) for item in entries), default=None),
            round(avg - previous, 2) if avg is not None and previous is not None else None,
            len(dates - completed),
        ))
        previous = avg
    return stats


def _remove_reminders(db: Session, plan: RecoveryPlan, now: datetime) -> None:
    # Reminders are user-scoped in the current schema; only one plan is active.
    db.execute(delete(Notification).where(
        Notification.user_id == plan.user_id, Notification.kind == "reminder",
        Notification.send_at >= now, Notification.read.is_(False),
    ))


def _reschedule(db: Session, plan: RecoveryPlan, now: datetime, weeks: int) -> None:
    """Preserve historical/today's and logged IDs; rebuild future work only."""
    logged = select(ExerciseSession.scheduled_session_id).where(
        ExerciseSession.scheduled_session_id.is_not(None),
    )
    db.execute(delete(ScheduledSession).where(
        ScheduledSession.plan_id == plan.id, ScheduledSession.scheduled_date > now.date(),
        ScheduledSession.id.not_in(logged),
    ))
    _remove_reminders(db, plan, now)
    remaining = set(db.scalars(select(ScheduledSession.scheduled_date).where(
        ScheduledSession.plan_id == plan.id,
    )))
    for day, week in build_schedule(plan.start_date, plan.frequency_per_week, weeks):
        if day <= now.date() or day in remaining:
            continue
        db.add(ScheduledSession(plan_id=plan.id, user_id=plan.user_id, scheduled_date=day, week_index=week))
        db.add(Notification(
            user_id=plan.user_id, kind="reminder", read=False,
            send_at=datetime.combine(day, time(9), tzinfo=UTC),
            message=f"Your updated LIMBER plan has a session on {day.isoformat()}.",
        ))


def reevaluate_plan(db: Session, plan: RecoveryPlan) -> ReevaluationDecision:
    """Caller holds the plan row lock and commits together with any session log."""
    now = utcnow()
    thresholds = get_thresholds()
    assessment = db.get(Assessment, plan.assessment_id)
    scope = check_scope(assessment.body_region, assessment.pain_level, assessment.red_flags, thresholds)
    logs = list(db.scalars(select(ExerciseSession).where(
        ExerciseSession.plan_id == plan.id, ExerciseSession.user_id == plan.user_id,
    )))
    reports = list(db.scalars(select(PainReport).join(
        ExerciseSession, PainReport.session_id == ExerciseSession.id,
    ).where(ExerciseSession.plan_id == plan.id, PainReport.user_id == plan.user_id)))
    urgent = list(scope.referral_reasons)
    if any(report.red_flags for report in reports):
        urgent.append("red_flag_reported")
    peak = max((max(item.pain_before, item.pain_after) for item in logs), default=0)
    if peak >= thresholds["reevaluation"]["referral_session_pain"]:
        urgent.append(f"session_pain_{peak}")
    weeks = completed_week_stats(db, plan, now.date())
    since = max(0, (now.date() - assessment.created_at.date()).days // 7)
    decision = Decision(Action.REFER, urgent) if urgent else evaluate(ReevaluationInput(
        weeks, assessment.pain_level, plan.difficulty_level, since,
    ), thresholds)

    # Check referral BEFORE the idempotency guard: new urgent data always wins.
    period_start = datetime.combine(plan.start_date + timedelta(weeks=len(weeks)), time(), tzinfo=UTC)
    previous = db.scalar(select(ReevaluationDecision).where(
        ReevaluationDecision.plan_id == plan.id, ReevaluationDecision.created_at >= period_start,
    ).order_by(ReevaluationDecision.id.desc()).limit(1))
    if decision.action != Action.REFER and previous is not None:
        return previous

    reasons = list(decision.reasons)
    if decision.action == Action.INCREASE:
        level = plan.difficulty_level + 1
        eligible = filter_exercises(
            list(db.scalars(select(Exercise))), assessment.body_region, assessment.limitations, level, thresholds,
        )
        try:
            items = build_fallback_plan(eligible, assessment.activity_difficulties, thresholds)
        except InsufficientExercisesError:
            decision = Decision(Action.REASSESS)
            reasons = ["insufficient_eligible_exercises_for_increase"]
        else:
            plan.items = [PlanItem(exercise_id=item.exercise_id, position=i, sets=item.sets, reps=item.reps)
                          for i, item in enumerate(items)]
            plan.difficulty_level = level
            plan.source = "fallback"
    elif decision.action == Action.REDUCE:
        if plan.frequency_per_week > 1:
            plan.frequency_per_week -= 1
        else:
            reasons.append("already_at_minimum_frequency")

    if decision.action == Action.REFER:
        plan.status = "referred"
        _remove_reminders(db, plan, now)
        message = "Please contact a licensed physical therapist. Your recovery plan has been stopped."
    elif decision.action == Action.REASSESS:
        plan.status = "reassessment_required"
        _remove_reminders(db, plan, now)
        message = "Please complete a new check-in before continuing your recovery plan."
    elif decision.action in (Action.REDUCE, Action.INCREASE):
        _reschedule(db, plan, now, max(thresholds["reevaluation"]["reassess_after_weeks"], len(weeks) + 1))
        message = (f"Your plan now uses level {plan.difficulty_level} exercises "
                   f"and {plan.frequency_per_week} sessions per week.")
    else:
        message = None
    record = ReevaluationDecision(
        user_id=plan.user_id, plan_id=plan.id, action=decision.action.value, reasons=reasons, created_at=now,
    )
    db.add(record)
    if message:
        db.add(Notification(
            user_id=plan.user_id, kind="referral" if decision.action == Action.REFER else "plan_update",
            message=message, send_at=now, read=False,
        ))
    db.flush()
    return record
