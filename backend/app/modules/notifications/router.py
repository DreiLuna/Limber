"""Notifications (APScheduler + SendGrid, later milestone)."""
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.modules.notifications.models import Notification
from app.modules.users.models import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    message: str
    send_at: datetime
    read: bool


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Notification]:
    return list(db.scalars(
        select(Notification).where(Notification.user_id == user.id).order_by(Notification.send_at.desc())
    ))
