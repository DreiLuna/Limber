"""Assessment and Rules boundary: planners receive only this approved exercise set."""
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import get_thresholds
from app.modules.assessment.scope import ScopeResult, check_scope
from app.modules.recommendation.filtering import ExerciseLike, filter_exercises


class AssessmentLike(Protocol):
    body_region: str
    pain_level: int
    red_flags: list[str]
    limitations: list[str]


@dataclass
class EligibilityResult:
    scope: ScopeResult
    exercises: list[ExerciseLike]
    can_generate_plan: bool


class EligibilityService:
    def __init__(self, thresholds: dict[str, Any] | None = None):
        self.thresholds = thresholds if thresholds is not None else get_thresholds()

    def evaluate(
        self, assessment: AssessmentLike, catalog: Sequence[ExerciseLike]
    ) -> EligibilityResult:
        # Recompute scope from the assessment rather than trusting a stored flag.
        scope = check_scope(
            assessment.body_region, assessment.pain_level, assessment.red_flags, self.thresholds
        )
        if not scope.in_scope or scope.starting_difficulty is None:
            return EligibilityResult(scope, [], False)
        exercises = filter_exercises(
            catalog, assessment.body_region, assessment.limitations,
            scope.starting_difficulty, self.thresholds,
        )
        return EligibilityResult(
            scope, exercises, len(exercises) >= self.thresholds["plan"]["min_exercises"]
        )
