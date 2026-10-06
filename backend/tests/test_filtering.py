import copy

import pytest

from app.modules.recommendation.filtering import (
    InsufficientExercisesError,
    build_fallback_plan,
    filter_exercises,
    rank_for_fallback,
)
from tests.conftest import Ex


def _catalog():
    return [
        Ex("knee_a", ["knee"], 1, targets_activities=["walking"]),
        Ex("knee_b", ["knee"], 1, ["cannot_kneel"], ["walking", "climbing_stairs"]),
        Ex("knee_c", ["knee"], 2),
        Ex("knee_d", ["knee", "lower_back"], 1, ["cannot_lie_on_floor"]),
        Ex("back_a", ["lower_back"], 1),
        Ex("ankle_a", ["ankle"], 3),
    ]


def test_region_filter(t):
    ids = {e.id for e in filter_exercises(_catalog(), "knee", [], 1, t)}
    assert ids == {"knee_a", "knee_b", "knee_d"}


def test_limitations_remove_contraindicated(t):
    ids = {e.id for e in filter_exercises(_catalog(), "knee", ["cannot_kneel", "cannot_lie_on_floor"], 1, t)}
    assert ids == {"knee_a"}


def test_exact_difficulty(t):
    ids = {e.id for e in filter_exercises(_catalog(), "knee", [], 2, t)}
    assert ids == {"knee_c"}


def test_at_most_difficulty_mode(t):
    t2 = copy.deepcopy(t)
    t2["filtering"]["difficulty_match"] = "at_most"
    ids = {e.id for e in filter_exercises(_catalog(), "knee", [], 2, t2)}
    assert ids == {"knee_a", "knee_b", "knee_c", "knee_d"}


def test_fallback_ranks_difficulty_then_activity_matches_then_id():
    pool = [Ex("z", ["knee"], 2, targets_activities=["walking", "squatting"]),
            Ex("y", ["knee"], 1),
            Ex("x", ["knee"], 1, targets_activities=["walking"]),
            Ex("w", ["knee"], 1, targets_activities=["walking", "squatting"])]
    ranked = [e.id for e in rank_for_fallback(pool, ["walking", "squatting"])]
    assert ranked == ["w", "x", "y", "z"]


def test_fallback_plan_size_and_conservative_params(t):
    pool = [Ex(f"e{i}", ["knee"], 1, sets_min=2, reps_min=10) for i in range(10)]
    plan = build_fallback_plan(pool, [], t)
    assert len(plan) == t["plan"]["max_exercises"]
    assert all(p.sets == 2 and p.reps == 10 for p in plan)


def test_fallback_insufficient_raises(t):
    with pytest.raises(InsufficientExercisesError):
        build_fallback_plan([Ex("a", ["knee"])], [], t)
