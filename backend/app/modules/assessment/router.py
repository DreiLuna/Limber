from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.modules.assessment.eligibility import EligibilityService
from app.modules.assessment.models import Assessment
from app.modules.assessment.schemas import AssessmentCreate, AssessmentOut, EligibilityOut
from app.modules.assessment.scope import check_scope
from app.modules.catalog.models import Exercise
from app.modules.plans.models import RecoveryPlan
from app.modules.users.models import User

router = APIRouter(prefix="/assessments", tags=["assessment"])


@router.post("", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
def create_assessment(
    body: AssessmentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Assessment:
    result = check_scope(body.body_region, body.pain_level, list(body.red_flags))
    assessment = Assessment(
        user_id=user.id,
        body_region=body.body_region,
        pain_level=body.pain_level,
        limitations=list(body.limitations),
        activity_difficulties=list(body.activity_difficulties),
        red_flags=list(body.red_flags),
        description=body.description,
        in_scope=result.in_scope,
        referral_reasons=result.referral_reasons,
        starting_difficulty=result.starting_difficulty,
    )
    db.add(assessment)
    if not result.in_scope:
        # Save the referral and retire existing plans in the same transaction.
        for plan in db.scalars(select(RecoveryPlan).where(
            RecoveryPlan.user_id == user.id, RecoveryPlan.status == "active"
        )):
            plan.status = "referred"
    db.commit()
    return assessment


@router.get("/latest", response_model=AssessmentOut)
def latest_assessment(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Assessment:
    a = db.scalar(
        select(Assessment).where(Assessment.user_id == user.id).order_by(Assessment.id.desc()).limit(1)
    )
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No assessment yet")
    return a


@router.get("/latest/eligibility", response_model=EligibilityOut)
def latest_eligibility(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> EligibilityOut:
    assessment = latest_assessment(user, db)
    result = EligibilityService().evaluate(assessment, db.scalars(select(Exercise)).all())
    return EligibilityOut(
        assessment_id=assessment.id,
        in_scope=result.scope.in_scope,
        referral_reasons=result.scope.referral_reasons,
        starting_difficulty=result.scope.starting_difficulty,
        can_generate_plan=result.can_generate_plan,
        eligible_exercises=result.exercises,
    )
