"""AI planning service interface (M5).

The rest of the app calls `plan_with_fallback`, which:
  1. asks the configured LLM client for a plan over the *already filtered* set,
  2. validates the response,
  3. falls back to the deterministic planner if the client is missing, fails,
     or returns anything invalid.

`get_planner_client()` returns None unless LLM_PROVIDER and LLM_API_KEY are set,
so by default every plan comes from the fallback.
"""
import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import get_settings, get_thresholds
from app.modules.ai.validation import AIPlanOutput, validate_plan
from app.modules.recommendation.filtering import (
    ExerciseLike,
    PlannedExercise,
    build_fallback_plan,
)

logger = logging.getLogger(__name__)


class PlannerClient(Protocol):
    def propose_plan(self, eligible: list[dict[str, Any]], context: dict[str, Any]) -> dict | str:
        """Return JSON matching ai.validation.AIPlanOutput. May raise on timeout or error."""
        ...


def build_plan_prompt(
    eligible: list[dict[str, Any]], context: dict[str, Any], t: dict[str, Any] | None = None
) -> str:
    t = t or get_thresholds()
    lo, hi = t["plan"]["min_exercises"], t["plan"]["max_exercises"]
    return (
        "You are helping build a home exercise plan for a recovery app.\n"
        f"Choose between {lo} and {hi} exercises from the ELIGIBLE list below.\n"
        "Rules:\n"
        "- Use only exercise ids that appear in ELIGIBLE; never invent ids or repeat one.\n"
        "- For each exercise, sets must be within its [min, max] 'sets' range and reps "
        "within its [min, max] 'reps' range.\n"
        "- Prefer exercises whose targets_activities match the user's activity difficulties.\n"
        "- Keep the rationale to one or two plain sentences.\n\n"
        f"USER CONTEXT:\n{json.dumps(context, sort_keys=True)}\n\n"
        f"ELIGIBLE:\n{json.dumps(eligible, sort_keys=True)}\n"
    )


class GeminiPlannerClient:
    """Asks Gemini for a plan as structured JSON. Output is still validated by the caller."""

    def __init__(self, api_key: str, model: str, timeout_s: int, sdk_client: Any | None = None):
        if sdk_client is None:
            from google import genai
            from google.genai import types

            sdk_client = genai.Client(
                api_key=api_key, http_options=types.HttpOptions(timeout=timeout_s * 1000)
            )
        self._client = sdk_client
        self._model = model

    def propose_plan(self, eligible: list[dict[str, Any]], context: dict[str, Any]) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=build_plan_prompt(eligible, context),
            config={
                "response_mime_type": "application/json",
                "response_schema": AIPlanOutput,
                "temperature": 0.2,
            },
        )
        text = response.text
        if not text:
            raise ValueError("empty LLM response")
        return text


def get_planner_client() -> PlannerClient | None:
    s = get_settings()
    if not s.llm_provider or not s.llm_api_key:
        return None
    provider = s.llm_provider.strip().lower()
    if provider != "gemini":
        logger.warning("Unsupported LLM_PROVIDER %r; using rule-based fallback", s.llm_provider)
        return None
    try:
        return GeminiPlannerClient(s.llm_api_key, s.llm_model, s.llm_timeout_s)
    except Exception:  # noqa: BLE001 - a broken client must never break plan creation
        logger.exception("Could not create Gemini client; using rule-based fallback")
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
