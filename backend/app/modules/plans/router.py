from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_thresholds
from app.core.database import get_db
from app.core.deps import get_current_user
from app.modules.ai.models import AIOutputLog
from app.modules.ai.planner import get_planner_client, plan_with_fallback
from app.modules.assessment.eligibility import EligibilityService
from app.modules.assessment.models import Assessment
from app.modules.catalog.models import Exercise
from app.modules.plans.models import PlanItem, RecoveryPlan, ScheduledSession
from app.modules.plans.scheduling import build_schedule
from app.modules.plans.schemas import PlanOut
from app.modules.recommendation.filtering import InsufficientExercisesError
from app.modules.users.models import User

router = APIRouter(prefix="/plans", tags=["plans"])


@router.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RecoveryPlan:
    """Create a plan from the user's latest assessment: scope -> filter -> AI or fallback -> schedule."""
    t = get_thresholds()
    assessment = db.scalar(
        select(Assessment).where(Assessment.user_id == user.id).order_by(Assessment.id.desc()).limit(1)
    )
    if assessment is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Complete an assessment first")
    eligibility = EligibilityService(t).evaluate(assessment, db.scalars(select(Exercise)).all())
    if not eligibility.scope.in_scope:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"message": "Out of scope: see a licensed physical therapist",
             "referral_reasons": eligibility.scope.referral_reasons},
        )

    eligible = eligibility.exercises
    client = get_planner_client()
    try:
        result = plan_with_fallback(eligible, assessment.activity_difficulties, client)
    except InsufficientExercisesError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"message": "Not enough approved exercises for this case: see a licensed physical therapist",
             "detail": str(exc)},
        ) from exc

    if client is not None:
        db.add(AIOutputLog(
            user_id=user.id, task="plan", request={"assessment_id": assessment.id},
            response=(result.ai_response if isinstance(result.ai_response, dict)
                      else {"raw": result.ai_response}),
            valid=result.source == "ai", errors=result.ai_errors,
            used_fallback=result.source == "fallback", latency_ms=result.latency_ms,
        ))

    # Only one active plan per user.
    for old in db.scalars(select(RecoveryPlan).where(
        RecoveryPlan.user_id == user.id, RecoveryPlan.status == "active"
    )):
        old.status = "superseded"

    freq = t["plan"]["default_frequency_per_week"]
    start = date.today()
    plan = RecoveryPlan(
        user_id=user.id, assessment_id=assessment.id, difficulty_level=eligibility.scope.starting_difficulty,
        frequency_per_week=freq, source=result.source, start_date=start,
    )
    plan.items = [
        PlanItem(exercise_id=p.exercise_id, position=i, sets=p.sets, reps=p.reps)
        for i, p in enumerate(result.exercises)
    ]
    plan.schedule = [
        ScheduledSession(user_id=user.id, scheduled_date=d, week_index=w)
        for d, w in build_schedule(start, freq, t["reevaluation"]["reassess_after_weeks"])
    ]
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/current", response_model=PlanOut)
def current_plan(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RecoveryPlan:
    plan = db.scalar(
        select(RecoveryPlan)
        .where(RecoveryPlan.user_id == user.id, RecoveryPlan.status == "active")
        .order_by(RecoveryPlan.id.desc())
        .limit(1)
    )
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active plan")
    return plan
