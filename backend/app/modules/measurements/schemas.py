from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# These IDs refer to the reviewed, versioned camera protocols, not arbitrary poses.
SUPPORTED_EXERCISES = {"Bodyweight_Squat", "Seated_Knee_Extension", "Wall_Press_Up"}


class MeasurementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    exercise_id: Literal["Bodyweight_Squat", "Seated_Knee_Extension", "Wall_Press_Up"]
    protocol: Literal["movement-v1"]
    side: Literal["left", "right"]
    reps: int = Field(strict=True, ge=0, le=500)
    partials: int = Field(strict=True, ge=0, le=500)
    hold_seconds: float = Field(ge=0, le=1800)
    min_angle: float = Field(ge=0, le=180)
    max_angle: float = Field(ge=0, le=180)
    tracking_ratio: float = Field(ge=0, le=1)
    duration_seconds: float = Field(ge=1, le=1800)

    @model_validator(mode="after")
    def plausible_summary(self):
        if self.min_angle > self.max_angle or self.hold_seconds > self.duration_seconds:
            raise ValueError("Invalid angle range or hold duration")
        if self.reps * 0.8 > self.duration_seconds or (self.reps and self.max_angle - self.min_angle < 10):
            raise ValueError("Repetitions are inconsistent with duration or movement range")
        return self


class MeasurementOut(MeasurementCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    target_reps: int
    created_at: datetime
