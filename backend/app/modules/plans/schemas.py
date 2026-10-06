from datetime import date

from pydantic import BaseModel, ConfigDict


class PlanItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exercise_id: str
    position: int
    sets: int
    reps: int


class ScheduledSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scheduled_date: date
    week_index: int


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: int
    status: str
    difficulty_level: int
    frequency_per_week: int
    source: str
    start_date: date
    items: list[PlanItemOut]
    schedule: list[ScheduledSessionOut]
