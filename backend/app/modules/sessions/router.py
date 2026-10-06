"""Exercise Session module (M3, Member 3). Contract defined; implementation pending."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user
from app.modules.sessions.schemas import SessionCreate, SessionOut
from app.modules.users.models import User

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def log_session(body: SessionCreate, user: User = Depends(get_current_user)) -> SessionOut:
    # TODO(M3): attach to the user's active plan, store ExerciseSession, store a PainReport
    # if new_red_flags is non-empty, then trigger reevaluation if a red flag was reported.
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Session logging lands in M3")


@router.get("", response_model=list[SessionOut])
def list_sessions(user: User = Depends(get_current_user)) -> list[SessionOut]:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Session history lands in M3")
