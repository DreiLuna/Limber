import json
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.modules.ai import planner
from app.modules.ai.planner import (
    GeminiPlannerClient,
    _catalog_view,
    build_plan_prompt,
    get_planner_client,
    plan_with_fallback,
)
from app.modules.ai.validation import AIPlanOutput
from tests.conftest import Ex

ELIGIBLE = [Ex(f"e{i}", ["knee"], 1, sets_min=1, sets_max=3, reps_min=8, reps_max=12) for i in range(6)]
CONTEXT = {"body_region": "knee", "limitations": [], "activity_difficulties": ["stairs"]}


class _FakeModels:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=self.text)


def _fake_sdk(text):
    return SimpleNamespace(models=_FakeModels(text))


def _valid_json():
    return json.dumps({
        "exercises": [{"exercise_id": f"e{i}", "sets": 2, "reps": 10} for i in range(4)],
        "rationale": "Gentle knee work.",
    })


def _settings(monkeypatch, **overrides):
    monkeypatch.setattr(planner, "get_settings", lambda: Settings(**overrides))


def test_default_settings_have_no_api_key():
    assert Settings.model_fields["llm_api_key"].default == ""


def test_no_provider_means_no_client(monkeypatch):
    _settings(monkeypatch, llm_provider="", llm_api_key="")
    assert get_planner_client() is None


def test_provider_without_key_means_no_client(monkeypatch):
    _settings(monkeypatch, llm_provider="gemini", llm_api_key="")
    assert get_planner_client() is None


def test_unknown_provider_means_no_client(monkeypatch):
    _settings(monkeypatch, llm_provider="something-else", llm_api_key="k")
    assert get_planner_client() is None


def test_gemini_provider_builds_client(monkeypatch):
    _settings(monkeypatch, llm_provider="Gemini", llm_api_key="test-key", llm_model="m")
    assert isinstance(get_planner_client(), GeminiPlannerClient)


def test_client_construction_failure_falls_back(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("bad config")

    _settings(monkeypatch, llm_provider="gemini", llm_api_key="test-key")
    monkeypatch.setattr(planner, "GeminiPlannerClient", boom)
    assert get_planner_client() is None


def test_prompt_contains_eligible_ids_context_and_limits(t):
    prompt = build_plan_prompt([_catalog_view(e) for e in ELIGIBLE], CONTEXT, t)
    for e in ELIGIBLE:
        assert f'"{e.id}"' in prompt
    assert "stairs" in prompt
    assert f"between {t['plan']['min_exercises']} and {t['plan']['max_exercises']}" in prompt


def test_gemini_client_requests_structured_json():
    sdk = _fake_sdk(_valid_json())
    out = GeminiPlannerClient("k", "test-model", 5, sdk_client=sdk).propose_plan(
        [_catalog_view(e) for e in ELIGIBLE], CONTEXT
    )
    assert out == _valid_json()
    call = sdk.models.calls[0]
    assert call["model"] == "test-model"
    assert call["config"]["response_mime_type"] == "application/json"
    assert call["config"]["response_schema"] is AIPlanOutput


def test_gemini_empty_response_raises():
    with pytest.raises(ValueError):
        GeminiPlannerClient("k", "m", 5, sdk_client=_fake_sdk("")).propose_plan([], {})


def test_valid_gemini_plan_is_used():
    client = GeminiPlannerClient("k", "m", 5, sdk_client=_fake_sdk(_valid_json()))
    r = plan_with_fallback(ELIGIBLE, [], client, CONTEXT)
    assert r.source == "ai" and [p.exercise_id for p in r.exercises] == ["e0", "e1", "e2", "e3"]


def test_malformed_gemini_json_falls_back():
    client = GeminiPlannerClient("k", "m", 5, sdk_client=_fake_sdk("{not json"))
    r = plan_with_fallback(ELIGIBLE, [], client, CONTEXT)
    assert r.source == "fallback" and r.ai_errors
    assert {p.exercise_id for p in r.exercises} <= {e.id for e in ELIGIBLE}

