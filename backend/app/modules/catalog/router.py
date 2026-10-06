from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.vocab import BodyRegion
from app.modules.catalog.models import Exercise
from app.modules.catalog.schemas import ExerciseOut

router = APIRouter(prefix="/exercises", tags=["catalog"])


@router.get("", response_model=list[ExerciseOut])
def list_exercises(
    region: BodyRegion | None = None, difficulty: int | None = None, db: Session = Depends(get_db)
) -> list[Exercise]:
    rows = db.scalars(select(Exercise).order_by(Exercise.id)).all()
    # JSON columns are filtered in Python so the same code works on SQLite and Postgres.
    if region:
        rows = [e for e in rows if region in e.body_regions]
    if difficulty:
        rows = [e for e in rows if e.difficulty == difficulty]
    return rows


@router.get("/{exercise_id}", response_model=ExerciseOut)
def get_exercise(exercise_id: str, db: Session = Depends(get_db)) -> Exercise:
    ex = db.get(Exercise, exercise_id)
    if ex is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercise not found")
    return ex
