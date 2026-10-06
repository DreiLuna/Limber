from pydantic import BaseModel


class WeekStatsOut(BaseModel):
    week_index: int
    completion_rate: float
    avg_post_pain: float | None
    max_session_pain: int | None
    pain_change: float | None
    missed_sessions: int


class ProgressOut(BaseModel):
    plan_id: int
    weeks: list[WeekStatsOut]
    explanation: str  # AI text if it validated, else a template
