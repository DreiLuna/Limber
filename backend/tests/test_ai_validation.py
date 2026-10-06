from app.modules.ai.planner import plan_with_fallback
from app.modules.ai.validation import (
    validate_adjustment,
    validate_explanation,
    validate_intake_suggestion,
    validate_plan,
)
from tests.conftest import Ex

ELIGIBLE = [Ex(f"e{i}", ["knee"], 1, sets_min=1, sets_max=3, reps_min=8, reps_max=12) for i in range(6)]


def plan(*items):
    return {"exercises": [{"exercise_id": i, "sets": s, "reps": r} for i, s, r in items]}


def test_valid_plan(t):
    assert validate_plan(plan(*[(f"e{i}", 2, 10) for i in range(4)]), ELIGIBLE, t).valid


def test_plan_with_ineligible_exercise(t):
    r = validate_plan(plan(("e0", 2, 10), ("e1", 2, 10), ("e2", 2, 10), ("deadlift", 2, 10)), ELIGIBLE, t)
    assert not r.valid and "not_eligible:deadlift" in r.errors


def test_plan_sets_reps_out_of_range(t):
    r = validate_plan(plan(("e0", 5, 10), ("e1", 2, 30), ("e2", 2, 10), ("e3", 2, 10)), ELIGIBLE, t)
    assert {"sets_out_of_range:e0:5", "reps_out_of_range:e1:30"} <= set(r.errors)


def test_plan_wrong_count_and_duplicates(t):
    r = validate_plan(plan(("e0", 2, 10), ("e0", 2, 10)), ELIGIBLE, t)
    assert "duplicate_exercise_ids" in r.errors and any(e.startswith("count:") for e in r.errors)


def test_plan_malformed_json(t):
    assert not validate_plan("not json", ELIGIBLE, t).valid
    assert not validate_plan({"exercises": [{"exercise_id": "e0"}]}, ELIGIBLE, t).valid


def test_intake_suggestion():
    assert validate_intake_suggestion({"body_region": "knee", "limitations": ["cannot_kneel"]}).valid
    r = validate_intake_suggestion({"body_region": "elbow", "limitations": ["cannot_fly"]})
    assert not r.valid and len(r.errors) == 2


def test_adjustment_difficulty_jump(t):
    bad = {"kind": "change_difficulty", "new_difficulty": 3}
    good = {"kind": "change_difficulty", "new_difficulty": 2}
    assert not validate_adjustment(bad, 1, [], ELIGIBLE, t).valid
    assert validate_adjustment(good, 1, [], ELIGIBLE, t).valid


def test_adjustment_replacement_must_be_eligible(t):
    r = validate_adjustment(
        {"kind": "replace_exercise", "exercise_id": "e0", "replacement_exercise_id": "zzz"},
        1, ["e0", "e1"], ELIGIBLE, t,
    )
    assert "not_eligible:zzz" in r.errors


def test_explanation_numbers_must_match():
    stored = [2, 0.83, 3.5, -1.0]
    assert validate_explanation("In week 2 you finished 83% of sessions and pain fell by 1.0 to 3.5.", stored).valid
    r = validate_explanation("You finished 90% of sessions.", stored)
    assert not r.valid and r.errors == ["unverified_number:90"]


# Planner fallback wiring
class _Raises:
    def propose_plan(self, eligible, context):
        raise TimeoutError


class _Returns:
    def __init__(self, out):
        self.out = out

    def propose_plan(self, eligible, context):
        return self.out


def test_no_client_uses_fallback():
    assert plan_with_fallback(ELIGIBLE, []).source == "fallback"


def test_client_error_uses_fallback():
    r = plan_with_fallback(ELIGIBLE, [], _Raises())
    assert r.source == "fallback" and r.ai_errors == ["client_error:TimeoutError"]


def test_invalid_ai_output_discarded():
    r = plan_with_fallback(ELIGIBLE, [], _Returns(plan(("hack", 9, 99))))
    assert r.source == "fallback" and r.ai_errors
    assert {p.exercise_id for p in r.exercises} <= {e.id for e in ELIGIBLE}


def test_valid_ai_output_used():
    out = plan(("e5", 3, 12), ("e4", 1, 8), ("e3", 2, 10), ("e2", 2, 10))
    r = plan_with_fallback(ELIGIBLE, [], _Returns(out))
    assert r.source == "ai" and [p.exercise_id for p in r.exercises] == ["e5", "e4", "e3", "e2"]
