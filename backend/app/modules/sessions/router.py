"""Exercise session logging and history."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_thresholds
from app.core.database import get_db, utcnow
from app.core.deps import get_current_user
from app.modules.notifications.models import Notification
from app.modules.plans.models import RecoveryPlan, ScheduledSession
from app.modules.sessions.models import ExerciseSession, PainReport
from app.modules.sessions.schemas import SessionCreate, SessionOut
from app.modules.users.models import User

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def log_session(
    body: SessionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SessionOut:
    plan = db.scalar(select(RecoveryPlan).where(
        RecoveryPlan.user_id == user.id, RecoveryPlan.status == "active"
    ).order_by(RecoveryPlan.id.desc()).limit(1))
    if plan is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Create an active plan before logging a session")

    scheduled = None
    if body.scheduled_session_id is not None:
        scheduled = db.scalar(select(ScheduledSession).where(
            ScheduledSession.id == body.scheduled_session_id,
            ScheduledSession.plan_id == plan.id,
            ScheduledSession.user_id == user.id,
        ))
        if scheduled is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Scheduled session not found")
        if scheduled.scheduled_date > utcnow().date():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "You cannot log a future session")
        existing = db.scalar(select(ExerciseSession).where(
            ExerciseSession.scheduled_session_id == scheduled.id
        ))
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "This scheduled session was already logged")

    session = ExerciseSession(
        user_id=user.id, plan_id=plan.id, scheduled_session_id=scheduled.id if scheduled else None,
        completed=body.completed, pain_before=body.pain_before, pain_after=body.pain_after,
        perceived_difficulty=body.perceived_difficulty,
        too_difficult_exercise_ids=body.too_difficult_exercise_ids, notes=body.notes,
    )
    db.add(session)
    db.flush()
    db.add(PainReport(
        user_id=user.id, session_id=session.id, pain_level=body.pain_after,
        red_flags=[flag.value for flag in body.new_red_flags],
    ))

    thresholds = get_thresholds()["reevaluation"]
    if body.new_red_flags or body.pain_after >= thresholds["referral_session_pain"]:
        reason = "new warning symptoms" if body.new_red_flags else f"pain of {body.pain_after}/10 after a session"
        db.add(Notification(
            user_id=user.id, kind="referral",
            message=f"Please contact a licensed physical therapist because you reported {reason}.",
            send_at=utcnow(), read=False,
        ))
    db.commit()
    db.refresh(session)
    return session


@router.get("", response_model=list[SessionOut])
def list_sessions(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ExerciseSession]:
    return list(db.scalars(select(ExerciseSession).where(
        ExerciseSession.user_id == user.id
    ).order_by(ExerciseSession.performed_at.desc(), ExerciseSession.id.desc())))
