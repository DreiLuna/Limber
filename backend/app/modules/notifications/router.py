"""In-app notifications and read state."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
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
        select(Notification).where(Notification.user_id == user.id).order_by(
            Notification.created_at.desc(), Notification.id.desc()
        )
    ))


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Notification:
    notification = db.scalar(select(Notification).where(
        Notification.id == notification_id, Notification.user_id == user.id
    ))
    if notification is None:
        raise HTTPException(404, "Notification not found")
    notification.read = True
    db.commit()
    db.refresh(notification)
    return notification
