from pydantic import BaseModel, ConfigDict


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    body_regions: list[str]
    difficulty: int
    category: str
    equipment: str | None
    instructions: list[str]
    sets_min: int
    sets_max: int
    reps_min: int
    reps_max: int
    media: list[str]
    contraindications: list[str]
    targets_activities: list[str]
