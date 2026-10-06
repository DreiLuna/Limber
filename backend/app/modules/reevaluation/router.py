"""Reevaluation module (M4, Member 3). Rules live in reevaluation.rules."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user
from app.modules.reevaluation.schemas import DecisionOut
from app.modules.users.models import User

router = APIRouter(prefix="/reevaluations", tags=["reevaluation"])


@router.post("", response_model=DecisionOut)
def reevaluate(user: User = Depends(get_current_user)) -> DecisionOut:
    # TODO(M4): build ReevaluationInput from ProgressRecords, call rules.evaluate,
    # store ReevaluationDecision, mark plan "referred" on REFER, notify the user.
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Reevaluation endpoint lands in M4")
