from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.modules.measurements.models import MovementMeasurement
from app.modules.measurements.schemas import MeasurementOut
from app.modules.users.models import User

router = APIRouter(prefix="/measurements", tags=["measurements"])


@router.get("", response_model=list[MeasurementOut])
def list_measurements(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(MovementMeasurement).where(
        MovementMeasurement.user_id == user.id,
    ).order_by(MovementMeasurement.created_at, MovementMeasurement.id)))
