"""Validation layer for every AI response. Nothing from the LLM reaches a user
unless it passes these checks; otherwise the caller uses the rule-based fallback
or a template explanation.

Checks (from the proposal):
  - exercise ids belong to the eligible set
  - sets and reps stay within catalog limits
  - any difficulty change stays within one level
  - suggested intake fields are supported values
  - every number in a progress explanation matches stored progress values
"""
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_thresholds
from app.core.vocab import ActivityDifficulty, BodyRegion, Limitation
from app.modules.recommendation.filtering import ExerciseLike


# ---- Structured output schemas the LLM must return -------------------------
class AIPlanExercise(BaseModel):
    exercise_id: str
    sets: int = Field(ge=1)
    reps: int = Field(ge=1)


class AIPlanOutput(BaseModel):
    exercises: list[AIPlanExercise]
    rationale: str = ""


class AIIntakeSuggestion(BaseModel):
    body_region: str | None = None
    limitations: list[str] = []
    activity_difficulties: list[str] = []


class AIAdjustment(BaseModel):
    kind: Literal["replace_exercise", "change_frequency", "change_difficulty"]
    exercise_id: str | None = None
    replacement_exercise_id: str | None = None
    new_frequency_per_week: int | None = Field(default=None, ge=1, le=7)
    new_difficulty: int | None = Field(default=None, ge=1, le=3)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    value: Any = None


def _parse(model: type[BaseModel], raw: dict | str) -> tuple[BaseModel | None, list[str]]:
    try:
        if isinstance(raw, str):
            return model.model_validate_json(raw), []
        return model.model_validate(raw), []
    except ValidationError as e:
        return None, [f"schema:{err['loc']}:{err['msg']}" for err in e.errors()]


# ---- Plan creation ---------------------------------------------------------
def validate_plan(
    raw: dict | str, eligible: Sequence[ExerciseLike], t: dict[str, Any] | None = None
) -> ValidationResult:
    t = t or get_thresholds()
    parsed, errors = _parse(AIPlanOutput, raw)
    if parsed is None:
        return ValidationResult(False, errors)

    by_id = {e.id: e for e in eligible}
    ids = [x.exercise_id for x in parsed.exercises]
    lo, hi = t["plan"]["min_exercises"], t["plan"]["max_exercises"]
    if not lo <= len(ids) <= hi:
        errors.append(f"count:{len(ids)} not in [{lo},{hi}]")
    if len(set(ids)) != len(ids):
        errors.append("duplicate_exercise_ids")
    for item in parsed.exercises:
        ex = by_id.get(item.exercise_id)
        if ex is None:
            errors.append(f"not_eligible:{item.exercise_id}")
            continue
        if not ex.sets_min <= item.sets <= ex.sets_max:
            errors.append(f"sets_out_of_range:{item.exercise_id}:{item.sets}")
        if not ex.reps_min <= item.reps <= ex.reps_max:
            errors.append(f"reps_out_of_range:{item.exercise_id}:{item.reps}")
    return ValidationResult(not errors, errors, parsed if not errors else None)


# ---- Intake interpretation -------------------------------------------------
def validate_intake_suggestion(raw: dict | str) -> ValidationResult:
    parsed, errors = _parse(AIIntakeSuggestion, raw)
    if parsed is None:
        return ValidationResult(False, errors)
    if parsed.body_region is not None and parsed.body_region not in set(BodyRegion):
        errors.append(f"unsupported_region:{parsed.body_region}")
    errors += [f"unsupported_limitation:{x}" for x in parsed.limitations if x not in set(Limitation)]
    errors += [
        f"unsupported_activity:{x}"
        for x in parsed.activity_difficulties
        if x not in set(ActivityDifficulty)
    ]
    return ValidationResult(not errors, errors, parsed if not errors else None)


# ---- Reevaluation adjustments ----------------------------------------------
def validate_adjustment(
    raw: dict | str,
    current_difficulty: int,
    current_exercise_ids: Iterable[str],
    eligible: Sequence[ExerciseLike],
    t: dict[str, Any] | None = None,
) -> ValidationResult:
    t = t or get_thresholds()
    parsed, errors = _parse(AIAdjustment, raw)
    if parsed is None:
        return ValidationResult(False, errors)
    eligible_ids = {e.id for e in eligible}
    current = set(current_exercise_ids)

    if parsed.kind == "replace_exercise":
        if parsed.exercise_id not in current:
            errors.append(f"not_in_plan:{parsed.exercise_id}")
        if parsed.replacement_exercise_id not in eligible_ids:
            errors.append(f"not_eligible:{parsed.replacement_exercise_id}")
        if parsed.replacement_exercise_id in current:
            errors.append(f"already_in_plan:{parsed.replacement_exercise_id}")
    elif parsed.kind == "change_frequency" and parsed.new_frequency_per_week is None:
        errors.append("missing:new_frequency_per_week")
    elif parsed.kind == "change_difficulty":
        if parsed.new_difficulty is None:
            errors.append("missing:new_difficulty")
        elif abs(parsed.new_difficulty - current_difficulty) > t["ai"]["max_difficulty_change"]:
            errors.append(f"difficulty_jump:{current_difficulty}->{parsed.new_difficulty}")
    return ValidationResult(not errors, errors, parsed if not errors else None)


# ---- Progress explanations -------------------------------------------------
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _allowed_numbers(values: Iterable[float | int | None]) -> set[float]:
    allowed: set[float] = set()
    for v in values:
        if v is None:
            continue
        v = float(v)
        allowed |= {round(v, 2), round(v, 1), float(round(v)), round(abs(v), 2), round(abs(v), 1)}
        if 0 <= v <= 1:  # rates may be written as percentages
            allowed |= {round(v * 100, 1), float(round(v * 100))}
    return allowed


def validate_explanation(text: str, stored_values: Iterable[float | int | None]) -> ValidationResult:
    """Every number in the text must match a stored progress value (rounding and
    percentage forms are allowed). Week numbers should be passed in stored_values too."""
    allowed = _allowed_numbers(stored_values)
    errors = [
        f"unverified_number:{n}"
        for n in _NUMBER.findall(text)
        if round(float(n), 2) not in allowed and round(float(n), 1) not in allowed
    ]
    return ValidationResult(not errors, errors, text if not errors else None)
