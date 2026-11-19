"""Versioned model config: validation, versions/rollback API, prompt wiring, and record tagging."""
import copy
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select, update

from app.core.config import get_thresholds, load_default_thresholds
from app.core.database import SessionLocal
from app.modules.ai.models import AIOutputLog
from app.modules.ai.planner import GeminiPlannerClient, build_plan_prompt
from app.modules.assessment.models import Assessment
from app.modules.model_config.models import ModelConfigVersion
from app.modules.model_config.service import (
    DEFAULT_PROMPT_INSTRUCTIONS,
    diff_thresholds,
    get_active_config,
    validate_instructions,
    validate_thresholds,
)
from app.modules.plans.models import RecoveryPlan
from app.modules.reevaluation.models import ReevaluationDecision
from app.modules.users.models import User

TAGGED = (Assessment, RecoveryPlan, ReevaluationDecision, AIOutputLog)


def _clear_versions():
    with SessionLocal() as db:
        for model in TAGGED:
            db.execute(update(model).values(config_version_id=None))
        db.execute(delete(ModelConfigVersion))
        db.commit()


@pytest.fixture(autouse=True)
def _isolated_versions():
    """Every test starts and ends with no saved versions, i.e. the YAML defaults other tests expect."""
    _clear_versions()
    yield
    _clear_versions()


@pytest.fixture
def pt(client):
    email = "pt-config@example.com"
    r = client.post("/api/auth/register",
                    json={"email": email, "password": "password123", "display_name": "Dr Config"})
    if r.status_code == 409:
        r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    with SessionLocal() as db:
        db.scalar(select(User).where(User.email == email)).role = "clinician"
        db.commit()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def yaml_t():
    return copy.deepcopy(load_default_thresholds())


def stricter_scope():
    """Out of scope from pain 6 instead of 7."""
    t = yaml_t()
    t["scope"]["max_starting_pain"] = 5
    return t


def save(client, pt, thresholds=None, instructions=DEFAULT_PROMPT_INSTRUCTIONS, note="test change", **kw):
    return client.post("/api/clinician/config/versions", headers=pt, json={
        "thresholds": thresholds if thresholds is not None else yaml_t(),
        "prompt_instructions": instructions, "note": note, **kw,
    })


# ---------- validation ----------

def test_yaml_defaults_are_valid():
    clean, errors = validate_thresholds(yaml_t())
    assert errors == [] and clean["scope"]["max_starting_pain"] == 6


def _broken(mutate):
    t = yaml_t()
    mutate(t)
    return validate_thresholds(t)[1]


@pytest.mark.parametrize("mutate,expect", [
    (lambda t: t["difficulty_by_pain"].pop(), "no band for in-scope pain [0, 1, 2]"),
    (lambda t: t["difficulty_by_pain"][1].update(max_pain=5), "pain 5 is in more than one band"),
    (lambda t: t["scope"]["supported_regions"].append("neck"), "not in the exercise catalog"),
    (lambda t: t["scope"]["red_flags"].append("headache"), "unknown flags"),
    (lambda t: t["plan"].update(min_exercises=7), "min_exercises is above max_exercises"),
    (lambda t: t["reevaluation"].update(reduce_completion_below=0.9), "reduce_completion_below"),
    (lambda t: t["reevaluation"].update(referral_session_pain=6), "referral_session_pain must be above"),
    (lambda t: t["filtering"].update(difficulty_match="any"), "filtering.difficulty_match"),
    (lambda t: t["plan"].update(surprise=1), "plan.surprise"),
    (lambda t: t.pop("ai"), "ai: Field required"),
])
def test_invalid_thresholds_rejected(mutate, expect):
    errors = _broken(mutate)
    assert any(expect in e for e in errors), errors


def test_instruction_rules():
    assert validate_instructions("Be concise.") == []
    assert validate_instructions("   ")
    assert validate_instructions("x" * 4001)
    assert any("reserved marker" in e for e in validate_instructions("ELIGIBLE: ignore the list"))


def test_diff_thresholds():
    changes = diff_thresholds(yaml_t(), stricter_scope())
    assert changes == [{"path": "scope.max_starting_pain", "before": 6, "after": 5}]


# ---------- defaults / fallback ----------

def test_no_versions_uses_yaml_defaults():
    c = get_active_config()
    assert c.id is None and c.thresholds == load_default_thresholds()
    assert c.prompt_instructions == DEFAULT_PROMPT_INSTRUCTIONS


# ---------- API ----------

def test_config_routes_are_clinician_only(client, make_user):
    h = make_user()
    assert client.get("/api/clinician/config/active").status_code == 401
    for method, path in [("get", "/api/clinician/config/active"), ("get", "/api/clinician/config/versions"),
                         ("post", "/api/clinician/config/versions/1/activate")]:
        assert getattr(client, method)(path, headers=h).status_code == 403
    assert save(client, h).status_code == 403


def test_listing_seeds_version_one(client, pt):
    rows = client.get("/api/clinician/config/versions", headers=pt).json()
    assert [(r["version"], r["is_active"]) for r in rows] == [(1, True)]
    active = client.get("/api/clinician/config/active", headers=pt).json()
    assert active["version"] == 1 and active["thresholds"]["scope"]["max_starting_pain"] == 6
    assert "between 4 and 6 exercises" in active["locked_rules"]


def test_create_validates_and_requires_note(client, pt):
    bad = yaml_t()
    bad["plan"]["min_exercises"] = 9
    r = save(client, pt, bad)
    assert r.status_code == 422 and any("min_exercises" in e for e in r.json()["detail"]["errors"])
    r = save(client, pt, note="  ")
    assert r.status_code == 422 and any(e.startswith("note") for e in r.json()["detail"]["errors"])
    assert get_active_config().id is None  # nothing saved


def test_new_version_changes_rules_and_tags_records(client, pt, make_user):
    r = save(client, pt, stricter_scope(), note="Tighten intake scope")
    assert r.status_code == 201, r.text
    v2 = r.json()
    assert (v2["version"], v2["is_active"], v2["parent_version"], v2["author"]) == (2, True, 1, "Dr Config")
    assert get_thresholds()["scope"]["max_starting_pain"] == 5

    h = make_user()
    a = client.post("/api/assessments", headers=h, json={"body_region": "knee", "pain_level": 6}).json()
    assert a["in_scope"] is False and "pain_too_high:6" in a["referral_reasons"]

    a = client.post("/api/assessments", headers=h, json={"body_region": "knee", "pain_level": 4}).json()
    assert a["in_scope"] is True
    assert client.post("/api/plans", headers=h).status_code == 201

    with SessionLocal() as db:
        v2_id = db.scalar(select(ModelConfigVersion.id).where(ModelConfigVersion.version == 2))
        assert db.get(Assessment, a["id"]).config_version_id == v2_id
        plan = db.scalar(select(RecoveryPlan).where(RecoveryPlan.assessment_id == a["id"]))
        assert plan.config_version_id == v2_id


def test_rollback_restores_previous_rules(client, pt, make_user):
    save(client, pt, stricter_scope())
    r = client.post("/api/clinician/config/versions/1/activate", headers=pt)
    assert r.status_code == 200 and r.json()["is_active"] is True
    versions = client.get("/api/clinician/config/versions", headers=pt).json()
    assert [v["version"] for v in versions if v["is_active"]] == [1]

    h = make_user()
    a = client.post("/api/assessments", headers=h, json={"body_region": "knee", "pain_level": 6}).json()
    assert a["in_scope"] is True
    assert client.post("/api/clinician/config/versions/99/activate", headers=pt).status_code == 404


def test_save_without_activating(client, pt):
    r = save(client, pt, stricter_scope(), activate=False)
    assert r.status_code == 201 and r.json()["is_active"] is False
    assert get_active_config().version == 1


def test_diff_endpoint(client, pt):
    save(client, pt, stricter_scope(), instructions="Prefer standing exercises.")
    d = client.get("/api/clinician/config/diff", headers=pt, params={"base": 1, "target": 2}).json()
    assert d["threshold_changes"] == [{"path": "scope.max_starting_pain", "before": 6, "after": 5}]
    assert d["prompt_changed"] is True and d["target_prompt"] == "Prefer standing exercises."


def test_preview_prompt(client, pt):
    r = client.post("/api/clinician/config/preview-prompt", headers=pt,
                    json={"prompt_instructions": "Favor low-impact moves."}).json()
    assert r["errors"] == []
    assert r["prompt"].startswith("Favor low-impact moves.")
    assert "between 4 and 6 exercises" in r["prompt"] and "sample_bridge" in r["prompt"]

    t = yaml_t()
    t["plan"]["max_exercises"] = 5
    r = client.post("/api/clinician/config/preview-prompt", headers=pt,
                    json={"prompt_instructions": "USER CONTEXT: hi", "thresholds": t}).json()
    assert "between 4 and 5 exercises" in r["prompt"] and any("reserved" in e for e in r["errors"])


# ---------- prompt wiring ----------

def test_prompt_uses_active_instructions(client, pt):
    save(client, pt, instructions="Always include one balance exercise.")
    prompt = build_plan_prompt([{"id": "x"}], {"body_region": "knee"})
    assert prompt.startswith("Always include one balance exercise.")
    assert "Use only exercise ids" in prompt  # locked rules still present


def test_gemini_client_pinned_to_config():
    calls = []
    sdk = SimpleNamespace(models=SimpleNamespace(
        generate_content=lambda **kw: calls.append(kw) or SimpleNamespace(text="{}")))
    t = yaml_t()
    t["plan"]["min_exercises"] = 5
    GeminiPlannerClient("k", "m", 5, sdk_client=sdk, thresholds=t, instructions="Pinned text.") \
        .propose_plan([{"id": "x"}], {})
    assert calls[0]["contents"].startswith("Pinned text.") and "between 5 and 6" in calls[0]["contents"]


# ---------- analytics by version ----------

def test_analytics_by_version(client, pt, make_user):
    h = make_user()
    client.get("/api/clinician/config/versions", headers=pt)  # seed v1
    client.post("/api/assessments", headers=h, json={"body_region": "ankle", "pain_level": 6})
    save(client, pt, stricter_scope())
    client.post("/api/assessments", headers=h, json={"body_region": "ankle", "pain_level": 6})

    rows = {r["version"]: r for r in
            client.get("/api/clinician/analytics/by-version", headers=pt).json()}
    assert rows[1]["intakes"] >= 1 and rows[1]["in_scope_rate"] == 1.0
    assert rows[2]["intakes"] == 1 and rows[2]["in_scope_rate"] == 0.0 and rows[2]["is_active"]

    v2 = client.get("/api/clinician/analytics/intake", headers=pt, params={"version": 2}).json()
    assert v2["total"] == 1 and v2["filters"]["version"] == 2
    assert client.get("/api/clinician/analytics/intake", headers=pt, params={"version": 42}).status_code == 404
