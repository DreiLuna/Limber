"""Authenticated reevaluation using saved sessions and deterministic rules."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.modules.plans.models import RecoveryPlan
from app.modules.reevaluation.models import ReevaluationDecision
from app.modules.reevaluation.schemas import DecisionOut
from app.modules.reevaluation.service import reevaluate_plan
from app.modules.users.models import User

router = APIRouter(prefix="/reevaluations", tags=["reevaluation"])


@router.post("", response_model=DecisionOut)
def reevaluate(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DecisionOut:
    plan = db.scalar(select(RecoveryPlan).where(
        RecoveryPlan.user_id == user.id,
    ).order_by(RecoveryPlan.id.desc()).limit(1).with_for_update())
    if plan is None:
        raise HTTPException(404, "No recovery plan")
    if plan.status in ("referred", "reassessment_required"):
        record = db.scalar(select(ReevaluationDecision).where(
            ReevaluationDecision.plan_id == plan.id, ReevaluationDecision.user_id == user.id,
        ).order_by(ReevaluationDecision.id.desc()).limit(1))
        if record is None:
            raise HTTPException(409, "Complete a new check-in before continuing")
    elif plan.status == "active":
        record = reevaluate_plan(db, plan)
        db.commit()
    else:
        raise HTTPException(409, "No active recovery plan")
    return DecisionOut(plan_id=plan.id, action=record.action, reasons=record.reasons)
