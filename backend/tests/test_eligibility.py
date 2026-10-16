from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.modules.assessment.eligibility import EligibilityService
from tests.conftest import Ex


def assessment(**changes):
    values = dict(body_region="knee", pain_level=5, red_flags=[], limitations=[])
    values.update(changes)
    return SimpleNamespace(**values)


def test_scope_blocks_all_exercises(t):
    result = EligibilityService(t).evaluate(assessment(red_flags=["numbness"]), [Ex("ok", ["knee"])])
    assert not result.scope.in_scope
    assert result.exercises == []
    assert not result.can_generate_plan


def test_filters_region_limitations_and_difficulty(t):
    catalog = [Ex("ok", ["knee"]), Ex("wrong_region", ["ankle"]),
               Ex("too_hard", ["knee"], difficulty=2),
               Ex("blocked", ["knee"], contraindications=["cannot_kneel"])]
    result = EligibilityService(t).evaluate(assessment(limitations=["cannot_kneel"]), catalog)
    assert [e.id for e in result.exercises] == ["ok"]
    assert result.scope.in_scope and not result.can_generate_plan


def test_minimum_exercise_boundary(t):
    catalog = [Ex(str(i), ["knee"]) for i in range(t["plan"]["min_exercises"])]
    service = EligibilityService(t)
    assert service.evaluate(assessment(), catalog).can_generate_plan
    assert not service.evaluate(assessment(), catalog[:-1]).can_generate_plan


def test_missing_difficulty_band_blocks_planning(t):
    custom = deepcopy(t)
    custom["difficulty_by_pain"] = []
    result = EligibilityService(custom).evaluate(assessment(), [Ex("ok", ["knee"])])
    assert result.exercises == [] and not result.can_generate_plan


@pytest.mark.parametrize("pain", [True, False, "5", 5.5, -1, 11])
def test_invalid_pain_rejected(client, make_user, pain):
    h = make_user()
    response = client.post("/api/assessments", headers=h, json={"body_region": "knee", "pain_level": pain})
    assert response.status_code == 422
    assert client.get("/api/assessments/latest", headers=h).status_code == 404


def test_preview_matches_plan_and_is_user_scoped(client, make_user):
    h = make_user()
    client.post("/api/assessments", headers=h, json={
        "body_region": "knee", "pain_level": 5, "limitations": ["cannot_kneel"]
    })
    preview = client.get("/api/assessments/latest/eligibility", headers=h)
    assert preview.status_code == 200
    data = preview.json()
    assert data["can_generate_plan"]
    approved = {e["id"] for e in data["eligible_exercises"]}
    plan = client.post("/api/plans", headers=h)
    assert plan.status_code == 201
    assert {e["exercise_id"] for e in plan.json()["items"]} <= approved
    assert client.get("/api/assessments/latest/eligibility", headers=make_user()).status_code == 404
    assert client.get("/api/assessments/latest/eligibility").status_code == 401


def test_out_of_scope_preview(client, make_user):
    h = make_user()
    client.post("/api/assessments", headers=h, json={"body_region": "neck", "pain_level": 5})
    data = client.get("/api/assessments/latest/eligibility", headers=h).json()
    assert not data["in_scope"] and not data["can_generate_plan"]
    assert data["eligible_exercises"] == []
    assert data["referral_reasons"] == ["unsupported_region:neck"]


def test_stored_scope_flag_cannot_bypass_current_rules(client, make_user, monkeypatch):
    from app.core.database import SessionLocal
    from app.modules.assessment.models import Assessment

    headers = make_user()
    created = client.post("/api/assessments", headers=headers, json={
        "body_region": "knee", "pain_level": 5,
    }).json()
    # Simulate a legacy/imported row whose cached scope no longer matches its data.
    with SessionLocal() as db:
        row = db.get(Assessment, created["id"])
        row.pain_level = 8
        row.in_scope = True
        row.starting_difficulty = 1
        db.commit()

    def unexpected_planner_call():
        pytest.fail("Out-of-scope data must be blocked before obtaining an AI client")

    monkeypatch.setattr("app.modules.plans.router.get_planner_client", unexpected_planner_call)
    preview = client.get("/api/assessments/latest/eligibility", headers=headers)
    assert preview.status_code == 200
    assert preview.json()["referral_reasons"] == ["pain_too_high:8"]
    assert preview.json()["eligible_exercises"] == []
    assert preview.json()["can_generate_plan"] is False
    planned = client.post("/api/plans", headers=headers)
    assert planned.status_code == 409
    assert planned.json()["detail"]["referral_reasons"] == ["pain_too_high:8"]
    assert client.get("/api/plans/current", headers=headers).status_code == 404


def test_insufficient_catalog_blocks_preview_and_plan(client, make_user, monkeypatch, t):
    headers = make_user()
    client.post("/api/assessments", headers=headers, json={
        "body_region": "knee", "pain_level": 5,
    })
    # Exceed the entire imported catalog to exercise the API's shortage path.
    monkeypatch.setitem(t["plan"], "min_exercises", 100_000)
    preview = client.get("/api/assessments/latest/eligibility", headers=headers)
    assert preview.status_code == 200
    assert preview.json()["in_scope"] is True
    assert preview.json()["can_generate_plan"] is False
    planned = client.post("/api/plans", headers=headers)
    assert planned.status_code == 409
    assert "Not enough approved exercises" in planned.json()["detail"]["message"]
    assert client.get("/api/plans/current", headers=headers).status_code == 404
