from pydantic import BaseModel


class DecisionOut(BaseModel):
    plan_id: int
    action: str  # refer, reduce, increase, reassess, continue
    reasons: list[str]
