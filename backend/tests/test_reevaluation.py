"""One or more cases per reevaluation rule, plus priority-order checks."""
from app.core.vocab import ReevaluationAction as Act
from app.modules.progress.metrics import WeekStats
from app.modules.reevaluation.rules import ReevaluationInput, evaluate


def wk(i, completion=1.0, pain=3.0, max_pain=None):
    return WeekStats(i, completion, pain, max_pain if max_pain is not None else int(pain), None, 0)


def run(weeks, intake=5, level=1, since=1, red=False, t=None):
    return evaluate(ReevaluationInput(weeks, intake, level, since, red), t)


# Rule 1: refer
def test_refer_on_session_pain_8(t):
    d = run([wk(0, pain=4, max_pain=8)], t=t)
    assert d.action == Act.REFER and "session_pain_8" in d.reasons


def test_refer_on_two_week_rise_of_2(t):
    assert run([wk(0, pain=3), wk(1, pain=4), wk(2, pain=5)], t=t).action == Act.REFER


def test_refer_on_red_flag(t):
    assert run([wk(0)], red=True, t=t).action == Act.REFER


def test_refer_after_six_weeks_without_improvement(t):
    weeks = [wk(i, pain=5) for i in range(6)]
    assert run(weeks, intake=5, t=t).action == Act.REFER


def test_no_refer_at_six_weeks_if_improved(t):
    weeks = [wk(i, pain=3) for i in range(6)]
    assert run(weeks, intake=5, since=1, t=t).action != Act.REFER


# Rule 2: reduce
def test_reduce_on_one_week_rise(t):
    assert run([wk(0, pain=3), wk(1, pain=4)], t=t).action == Act.REDUCE


def test_reduce_on_low_completion(t):
    assert run([wk(0, completion=0.33)], t=t).action == Act.REDUCE


# Rule 3: increase
def test_increase_on_stable_pain_and_high_completion(t):
    assert run([wk(0, 0.8, 3), wk(1, 1.0, 3)], t=t).action == Act.INCREASE


def test_no_increase_at_max_level(t):
    assert run([wk(0, 1.0, 3), wk(1, 1.0, 2)], level=3, t=t).action == Act.CONTINUE


def test_no_increase_with_only_one_week(t):
    assert run([wk(0, 1.0, 3)], t=t).action == Act.CONTINUE


# Rule 4: reassess
def test_reassess_after_four_weeks(t):
    weeks = [wk(0, 0.7, 3), wk(1, 0.7, 3), wk(2, 0.7, 3), wk(3, 0.7, 3)]
    assert run(weeks, since=4, t=t).action == Act.REASSESS


# Rule 5: continue
def test_continue_otherwise(t):
    assert run([wk(0, 0.7, 3)], t=t).action == Act.CONTINUE


# Priority order
def test_referral_beats_reduce(t):
    # one-week rise (reduce) and session pain 9 (refer) -> refer
    assert run([wk(0, pain=3), wk(1, pain=4, max_pain=9)], t=t).action == Act.REFER


def test_reduce_beats_reassess(t):
    assert run([wk(0, completion=0.2)], since=5, t=t).action == Act.REDUCE


def test_increase_beats_reassess(t):
    assert run([wk(0, 1.0, 3), wk(1, 1.0, 3)], since=4, t=t).action == Act.INCREASE
