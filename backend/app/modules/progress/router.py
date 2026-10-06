"""Progress Tracking module (M4, Member 3). Metrics live in progress.metrics."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user
from app.modules.progress.schemas import ProgressOut
from app.modules.users.models import User

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=ProgressOut)
def get_progress(user: User = Depends(get_current_user)) -> ProgressOut:
    # TODO(M4): load sessions for the active plan, run compute_weekly_stats, upsert ProgressRecord.
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Progress endpoint lands in M4")
