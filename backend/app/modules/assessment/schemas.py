from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.vocab import ActivityDifficulty, BodyRegion, Limitation, RedFlag
from app.modules.catalog.schemas import ExerciseOut


class AssessmentCreate(BaseModel):
    body_region: BodyRegion
    pain_level: int = Field(strict=True, ge=0, le=10)
    limitations: list[Limitation] = []
    activity_difficulties: list[ActivityDifficulty] = []
    red_flags: list[RedFlag] = []
    description: str | None = Field(default=None, max_length=2000)


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    body_region: str
    pain_level: int
    limitations: list[str]
    activity_difficulties: list[str]
    red_flags: list[str]
    description: str | None
    in_scope: bool
    referral_reasons: list[str]
    starting_difficulty: int | None
    created_at: datetime


class EligibilityOut(BaseModel):
    assessment_id: int
    in_scope: bool
    referral_reasons: list[str]
    starting_difficulty: int | None
    can_generate_plan: bool
    eligible_exercises: list[ExerciseOut]
