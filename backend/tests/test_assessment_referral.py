"""Referral assessments retire active plans without changing other users or history."""

import pytest

from app.core.database import SessionLocal
from app.modules.plans.models import RecoveryPlan


@pytest.mark.parametrize("referral", [
    {"body_region": "knee", "pain_level": 8},
    {"body_region": "neck", "pain_level": 3},
    {"body_region": "knee", "pain_level": 3, "red_flags": ["numbness"]},
])
def test_referral_retires_only_users_active_plan(client, make_user, referral):
    alice, bob = make_user(), make_user()
    plans = []
    for headers in (alice, alice, bob):
        assert client.post("/api/assessments", headers=headers, json={
            "body_region": "knee", "pain_level": 3,
        }).status_code == 201
        response = client.post("/api/plans", headers=headers)
        assert response.status_code == 201, response.text
        plans.append(response.json()["id"])

    response = client.post("/api/assessments", headers=alice, json=referral)
    assert response.status_code == 201, response.text
    assert response.json()["in_scope"] is False
    assert client.get("/api/plans/current", headers=alice).status_code == 404
    assert client.post("/api/plans", headers=alice).status_code == 409
    assert client.get("/api/plans/current", headers=bob).json()["id"] == plans[2]
    with SessionLocal() as db:
        assert [db.get(RecoveryPlan, plan_id).status for plan_id in plans] == [
            "superseded", "referred", "active",
        ]


def test_in_scope_reassessment_keeps_current_plan(client, make_user):
    headers = make_user()
    intake = {"body_region": "knee", "pain_level": 3}
    assert client.post("/api/assessments", headers=headers, json=intake).status_code == 201
    plan = client.post("/api/plans", headers=headers).json()
    assert client.post("/api/assessments", headers=headers, json=intake).status_code == 201
    current = client.get("/api/plans/current", headers=headers)
    assert current.status_code == 200
    assert current.json()["id"] == plan["id"]

