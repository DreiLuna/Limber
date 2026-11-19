"""Conservative evidence gate; camera estimates can block an increase, never override a referral."""
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.measurements.models import MovementMeasurement
from app.modules.measurements.schemas import SUPPORTED_EXERCISES
from app.modules.plans.models import RecoveryPlan, ScheduledSession
from app.modules.sessions.models import ExerciseSession


def progression_evidence(db: Session, plan: RecoveryPlan, finished_weeks: int, policy: dict) -> list[str]:
    required = {item.exercise_id for item in plan.items} & SUPPORTED_EXERCISES
    n = policy["weeks"]
    if finished_weeks < n or not required:
        return ["measured_progress_missing_supported_exercises_or_full_weeks"]
    weeks = range(finished_weeks - n, finished_weeks)
    schedule = list(db.scalars(select(ScheduledSession).where(
        ScheduledSession.plan_id == plan.id, ScheduledSession.week_index.in_(weeks),
    )))
    logs = list(db.scalars(select(ExerciseSession).where(
        ExerciseSession.plan_id == plan.id, ExerciseSession.user_id == plan.user_id,
    )))
    summaries = list(db.scalars(select(MovementMeasurement).join(
        ExerciseSession, MovementMeasurement.session_id == ExerciseSession.id,
    ).where(ExerciseSession.plan_id == plan.id, MovementMeasurement.user_id == plan.user_id)))
    by_session = {}
    for row in summaries:
        by_session.setdefault(row.session_id, {})[row.exercise_id] = row
    ranges = {}
    for week in weeks:
        due = {item.id for item in schedule if item.week_index == week}
        entries = [item for item in logs if item.scheduled_session_id in due]
        if any(max(item.pain_before, item.pain_after) > policy["pain_at_most"] for item in entries):
            return ["measured_progress_requires_low_pain"]
        qualifying = set()
        for entry in entries:
            rows = by_session.get(entry.id, {})
            if not entry.completed or not required.issubset(rows):
                continue
            good = all(
                row.reps >= row.target_reps and row.tracking_ratio >= policy["tracking_at_least"]
                and row.max_angle - row.min_angle >= policy["range_at_least_degrees"]
                and row.partials <= row.reps * policy["partials_at_most_ratio"]
                and row.duration_seconds >= policy["duration_at_least_seconds"]
                for key, row in rows.items() if key in required
            )
            if good:
                qualifying.add(entry.scheduled_session_id)
                for key in required:
                    row = rows[key]
                    ranges.setdefault((key, week), []).append((row.side, row.max_angle - row.min_angle))
        if not due or len(qualifying) / len(due) < policy["completion_at_least"]:
            return ["measured_progress_requires_two_complete_weeks"]
    for key in required:
        sides = {side for week in weeks for side, _ in ranges[(key, week)]}
        if len(sides) != 1:
            return ["measured_progress_requires_same_side"]
        values = [median(value for _, value in ranges[(key, week)]) for week in weeks]
        if any(b < a - policy["range_drop_at_most_degrees"] for a, b in zip(values, values[1:], strict=False)):
            return ["measured_progress_range_declined"]
    return []
