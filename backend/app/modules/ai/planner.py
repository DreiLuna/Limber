"""AI planning service interface (M5).

The rest of the app calls `plan_with_fallback`, which:
  1. asks the configured LLM client for a plan over the *already filtered* set,
  2. validates the response,
  3. falls back to the deterministic planner if the client is missing, fails,
     or returns anything invalid.

Until M5, `get_planner_client()` returns None, so every plan comes from the fallback.
"""
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import get_settings
from app.modules.ai.validation import validate_plan
from app.modules.recommendation.filtering import (
    ExerciseLike,
    PlannedExercise,
    build_fallback_plan,
)


class PlannerClient(Protocol):
    def propose_plan(self, eligible: list[dict[str, Any]], context: dict[str, Any]) -> dict | str:
        """Return JSON matching ai.validation.AIPlanOutput. May raise on timeout or error."""
        ...


def get_planner_client() -> PlannerClient | None:
    s = get_settings()
    if not s.llm_provider or not s.llm_api_key:
        return None
    # TODO(M5, Member 2): return a Claude or OpenAI client that requests structured JSON.
    return None


@dataclass
class PlanResult:
    exercises: list[PlannedExercise]
    source: str  # "ai" or "fallback"
    ai_response: dict | str | None
    ai_errors: list[str]
    latency_ms: int | None


def _catalog_view(e: ExerciseLike) -> dict[str, Any]:
    return {
        "id": e.id,
        "difficulty": e.difficulty,
        "sets": [e.sets_min, e.sets_max],
        "reps": [e.reps_min, e.reps_max],
        "targets_activities": e.targets_activities,
    }


def plan_with_fallback(
    eligible: Sequence[ExerciseLike],
    activity_difficulties: Sequence[str],
    client: PlannerClient | None = None,
    context: dict[str, Any] | None = None,
) -> PlanResult:
    if client is not None:
        start = time.perf_counter()
        try:
            raw = client.propose_plan([_catalog_view(e) for e in eligible], context or {})
        except Exception as exc:  # noqa: BLE001 - any client failure means fallback
            raw, errors = None, [f"client_error:{type(exc).__name__}"]
        else:
            result = validate_plan(raw, eligible)
            errors = result.errors
            if result.valid:
                planned = [PlannedExercise(x.exercise_id, x.sets, x.reps) for x in result.value.exercises]
                latency = int((time.perf_counter() - start) * 1000)
                return PlanResult(planned, "ai", raw, [], latency)
        latency = int((time.perf_counter() - start) * 1000)
        fallback = build_fallback_plan(eligible, activity_difficulties)
        return PlanResult(fallback, "fallback", raw, errors, latency)

    return PlanResult(build_fallback_plan(eligible, activity_difficulties), "fallback", None, [], None)
