"""Rule-based exercise filtering and the deterministic fallback planner.

Filtering runs before the AI ever sees anything. The order matches the proposal:
  1. keep exercises for the user's body region
  2. drop exercises contraindicated by the user's limitations
  3. keep only the user's starting difficulty level

The fallback planner is used whenever the AI is unavailable or its output fails
validation. It ranks by lowest difficulty first, then by how many of the user's
reported activity difficulties the exercise targets (more is better), then by id
so results are stable for testing.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import get_thresholds


class ExerciseLike(Protocol):
    id: str
    body_regions: list[str]
    difficulty: int
    contraindications: list[str]
    targets_activities: list[str]
    sets_min: int
    sets_max: int
    reps_min: int
    reps_max: int


@dataclass(frozen=True)
class PlannedExercise:
    exercise_id: str
    sets: int
    reps: int


class InsufficientExercisesError(Exception):
    """Fewer eligible exercises than plan.min_exercises. The caller should not
    create a plan and should treat the case like a scope failure."""


def filter_exercises(
    exercises: Sequence[ExerciseLike],
    body_region: str,
    limitations: Sequence[str],
    difficulty: int,
    t: dict[str, Any] | None = None,
) -> list[ExerciseLike]:
    t = t or get_thresholds()
    mode = t.get("filtering", {}).get("difficulty_match", "exact")
    limits = set(limitations)

    by_region = [e for e in exercises if body_region in e.body_regions]
    by_limits = [e for e in by_region if not limits.intersection(e.contraindications)]
    if mode == "at_most":
        return [e for e in by_limits if e.difficulty <= difficulty]
    return [e for e in by_limits if e.difficulty == difficulty]


def activity_match_count(exercise: ExerciseLike, activity_difficulties: Sequence[str]) -> int:
    return len(set(activity_difficulties).intersection(exercise.targets_activities))


def rank_for_fallback(
    eligible: Sequence[ExerciseLike], activity_difficulties: Sequence[str]
) -> list[ExerciseLike]:
    return sorted(
        eligible,
        key=lambda e: (e.difficulty, -activity_match_count(e, activity_difficulties), e.id),
    )


def build_fallback_plan(
    eligible: Sequence[ExerciseLike],
    activity_difficulties: Sequence[str],
    t: dict[str, Any] | None = None,
) -> list[PlannedExercise]:
    """Pick the top-ranked exercises and use the conservative end of each catalog range."""
    t = t or get_thresholds()
    lo, hi = t["plan"]["min_exercises"], t["plan"]["max_exercises"]
    if len(eligible) < lo:
        raise InsufficientExercisesError(f"only {len(eligible)} eligible exercises, need {lo}")
    ranked = rank_for_fallback(eligible, activity_difficulties)[:hi]
    return [PlannedExercise(e.id, sets=e.sets_min, reps=e.reps_min) for e in ranked]
