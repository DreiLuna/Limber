"""Weekly progress computed from the user's scheduled sessions and session logs."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db, utcnow
from app.core.deps import get_current_user
from app.modules.plans.models import RecoveryPlan, ScheduledSession
from app.modules.progress.metrics import SessionLog, compute_weekly_stats
from app.modules.progress.models import ProgressRecord
from app.modules.progress.schemas import ProgressOut
from app.modules.sessions.models import ExerciseSession
from app.modules.users.models import User

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=ProgressOut)
def get_progress(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProgressOut:
    plan = db.scalar(select(RecoveryPlan).where(
        RecoveryPlan.user_id == user.id, RecoveryPlan.status == "active"
    ).order_by(RecoveryPlan.id.desc()).limit(1))
    if plan is None:
        raise HTTPException(404, "No active plan")

    today = utcnow().date()
    due = list(db.scalars(select(ScheduledSession).where(
        ScheduledSession.plan_id == plan.id, ScheduledSession.scheduled_date <= today
    ).order_by(ScheduledSession.scheduled_date)))
    sessions = list(db.scalars(select(ExerciseSession).where(
        ExerciseSession.user_id == user.id, ExerciseSession.plan_id == plan.id
    ).order_by(ExerciseSession.performed_at)))
    schedule_counts: dict[int, int] = {}
    for item in due:
        schedule_counts[item.week_index] = schedule_counts.get(item.week_index, 0) + 1
    scheduled_by_id = {item.id: item.week_index for item in due}
    logs = []
    for item in sessions:
        week = scheduled_by_id.get(item.scheduled_session_id)
        if week is None:
            week = max(0, (item.performed_at.date() - plan.start_date).days // 7)
            schedule_counts.setdefault(week, 0)
        logs.append(SessionLog(week, item.completed, item.pain_after))

    stats = compute_weekly_stats(logs, schedule_counts)
    for week in stats:
        record = db.scalar(select(ProgressRecord).where(
            ProgressRecord.plan_id == plan.id, ProgressRecord.week_index == week.week_index
        ))
        values = dict(
            user_id=user.id, plan_id=plan.id, week_index=week.week_index,
            week_start=plan.start_date + timedelta(weeks=week.week_index),
            completion_rate=week.completion_rate, avg_post_pain=week.avg_post_pain,
            max_session_pain=week.max_session_pain, pain_change=week.pain_change,
            missed_sessions=week.missed_sessions,
        )
        if record:
            for key, value in values.items():
                setattr(record, key, value)
        else:
            db.add(ProgressRecord(**values))
    db.commit()
    explanation = "Log sessions to see your weekly completion and pain trends."
    if stats:
        latest = stats[-1]
        if latest.avg_post_pain is not None:
            if latest.pain_change is None or latest.pain_change == 0:
                direction = "about the same"
            else:
                direction = "lower" if latest.pain_change < 0 else "higher"
            completion = round(latest.completion_rate * 100)
            explanation = (
                f"This week, you completed {completion}% of sessions; average post-session pain "
                f"is {direction} than last week."
            )
        else:
            explanation = (
                f"You have {latest.missed_sessions} session(s) due this week. "
                "Log a session to track pain and completion."
            )
    return ProgressOut(plan_id=plan.id, weeks=[{
        "week_index": s.week_index, "completion_rate": s.completion_rate,
        "avg_post_pain": s.avg_post_pain, "max_session_pain": s.max_session_pain,
        "pain_change": s.pain_change, "missed_sessions": s.missed_sessions,
    } for s in stats], explanation=explanation)
