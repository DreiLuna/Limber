from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.vocab import RedFlag


class SessionCreate(BaseModel):
    scheduled_session_id: int | None = None
    completed: bool
    pain_before: int = Field(ge=0, le=10)
    pain_after: int = Field(ge=0, le=10)
    perceived_difficulty: int = Field(ge=1, le=5)
    too_difficult_exercise_ids: list[str] = Field(default_factory=list)
    new_red_flags: list[RedFlag] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    scheduled_session_id: int | None
    performed_at: datetime
    completed: bool
    pain_before: int
    pain_after: int
    perceived_difficulty: int
