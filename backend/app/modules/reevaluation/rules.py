"""Priority-ordered reevaluation rules. The first rule that fires wins.

  1. REFER     any session pain >= referral_session_pain in the latest week;
               weekly average pain up by >= referral_avg_pain_rise_two_weeks across
               the last two weeks (week[-1] vs week[-3]);
               a red-flag symptom reported;
               or, after referral_no_improvement_weeks on the plan, latest average
               pain is not below intake pain.
  2. REDUCE    weekly average pain up by >= reduce_avg_pain_rise_one_week, or
               latest completion below reduce_completion_below.
  3. INCREASE  the last increase_stable_weeks weeks all have completion >=
               increase_completion_at_least and pain never rose between them,
               and the plan is not already at level 3.
  4. REASSESS  weeks since the last assessment >= reassess_after_weeks.
  5. CONTINUE  otherwise.

The AI never calls this module's decisions into question; referral always wins.
"""
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_thresholds
from app.core.vocab import ReevaluationAction
from app.modules.progress.metrics import WeekStats

MAX_DIFFICULTY = 3


@dataclass(frozen=True)
class ReevaluationInput:
    weeks: Sequence[WeekStats]  # completed plan weeks, oldest first
    intake_pain: int
    current_difficulty: int
    weeks_since_assessment: int
    red_flag_reported: bool = False


@dataclass
class Decision:
    action: ReevaluationAction
    reasons: list[str] = field(default_factory=list)


def _avg(weeks: Sequence[WeekStats], i: int) -> float | None:
    return weeks[i].avg_post_pain if len(weeks) >= -i else None


def _referral_reasons(inp: ReevaluationInput, r: dict[str, Any]) -> list[str]:
    w = inp.weeks
    reasons: list[str] = []
    if inp.red_flag_reported:
        reasons.append("red_flag_reported")
    if w and w[-1].max_session_pain is not None and w[-1].max_session_pain >= r["referral_session_pain"]:
        reasons.append(f"session_pain_{w[-1].max_session_pain}")
    a1, a3 = _avg(w, -1), _avg(w, -3)
    if a1 is not None and a3 is not None and a1 - a3 >= r["referral_avg_pain_rise_two_weeks"]:
        reasons.append(f"avg_pain_rose_{a1 - a3:g}_over_two_weeks")
    if len(w) >= r["referral_no_improvement_weeks"] and a1 is not None and a1 >= inp.intake_pain:
        reasons.append(f"no_improvement_after_{len(w)}_weeks")
    return reasons


def _reduce_reasons(inp: ReevaluationInput, r: dict[str, Any]) -> list[str]:
    w = inp.weeks
    reasons: list[str] = []
    a1, a2 = _avg(w, -1), _avg(w, -2)
    if a1 is not None and a2 is not None and a1 - a2 >= r["reduce_avg_pain_rise_one_week"]:
        reasons.append(f"avg_pain_rose_{a1 - a2:g}_in_one_week")
    if w and w[-1].completion_rate < r["reduce_completion_below"]:
        reasons.append(f"completion_{w[-1].completion_rate:g}")
    return reasons


def _should_increase(inp: ReevaluationInput, r: dict[str, Any]) -> bool:
    n = r["increase_stable_weeks"]
    if inp.current_difficulty >= MAX_DIFFICULTY or len(inp.weeks) < n:
        return False
    recent = inp.weeks[-n:]
    if any(wk.completion_rate < r["increase_completion_at_least"] for wk in recent):
        return False
    pains = [wk.avg_post_pain for wk in recent]
    if any(p is None for p in pains):
        return False
    return all(later <= earlier for earlier, later in zip(pains, pains[1:], strict=False))


def evaluate(inp: ReevaluationInput, t: dict[str, Any] | None = None) -> Decision:
    r = (t or get_thresholds())["reevaluation"]

    if reasons := _referral_reasons(inp, r):
        return Decision(ReevaluationAction.REFER, reasons)
    if reasons := _reduce_reasons(inp, r):
        return Decision(ReevaluationAction.REDUCE, reasons)
    if _should_increase(inp, r):
        return Decision(ReevaluationAction.INCREASE, ["stable_pain_and_high_completion"])
    if inp.weeks_since_assessment >= r["reassess_after_weeks"]:
        return Decision(ReevaluationAction.REASSESS, [f"{inp.weeks_since_assessment}_weeks_since_assessment"])
    return Decision(ReevaluationAction.CONTINUE)
