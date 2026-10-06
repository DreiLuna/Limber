"""Deterministic scope check run on every intake, before any plan or AI call.

Out of scope (recommend a licensed physical therapist instead of a plan):
  - starting pain above scope.max_starting_pain (7+ by default)
  - a body region outside scope.supported_regions
  - any red-flag symptom
"""
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_thresholds


@dataclass
class ScopeResult:
    in_scope: bool
    referral_reasons: list[str] = field(default_factory=list)
    starting_difficulty: int | None = None


def starting_difficulty_for_pain(pain_level: int, t: dict[str, Any] | None = None) -> int | None:
    t = t or get_thresholds()
    for band in t["difficulty_by_pain"]:
        if band["min_pain"] <= pain_level <= band["max_pain"]:
            return band["level"]
    return None


def check_scope(
    body_region: str,
    pain_level: int,
    red_flags: list[str],
    t: dict[str, Any] | None = None,
) -> ScopeResult:
    t = t or get_thresholds()
    scope = t["scope"]
    reasons: list[str] = []

    if body_region not in scope["supported_regions"]:
        reasons.append(f"unsupported_region:{body_region}")
    if pain_level > scope["max_starting_pain"]:
        reasons.append(f"pain_too_high:{pain_level}")
    for flag in red_flags:
        if flag in scope["red_flags"]:
            reasons.append(f"red_flag:{flag}")

    if reasons:
        return ScopeResult(in_scope=False, referral_reasons=reasons)
    return ScopeResult(in_scope=True, starting_difficulty=starting_difficulty_for_pain(pain_level, t))
