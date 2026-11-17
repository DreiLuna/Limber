"""Referral assessments retire active plans without changing other users or history."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal, utcnow
from app.modules.notifications.models import Notification
from app.modules.plans.models import RecoveryPlan, ScheduledSession


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


@pytest.mark.parametrize("referral", [
    {"body_region": "knee", "pain_level": 8},
    {"body_region": "neck", "pain_level": 3},
    {"body_region": "knee", "pain_level": 3, "red_flags": ["numbness"]},
])
def test_referral_clears_pending_reminders_and_preserves_history(client, make_user, referral):
    alice, bob = make_user(), make_user()
    plans = []
    for headers in (alice, bob):
        client.post("/api/assessments", headers=headers, json={"body_region": "knee", "pain_level": 3})
        response = client.post("/api/plans", headers=headers)
        assert response.status_code == 201, response.text
        plans.append(response.json()["id"])

    logged = client.post("/api/sessions", headers=alice, json={
        "completed": True, "pain_before": 3, "pain_after": 2, "perceived_difficulty": 2,
    })
    assert logged.status_code == 201, logged.text
    now = utcnow()
    with SessionLocal() as db:
        user_id = db.get(RecoveryPlan, plans[0]).user_id
        preserved = [
            Notification(user_id=user_id, kind="reminder", message="Past reminder",
                         send_at=now - timedelta(days=1), read=False),
            Notification(user_id=user_id, kind="reminder", message="Read reminder",
                         send_at=now + timedelta(days=1), read=True),
            Notification(user_id=user_id, kind="plan_update", message="Plan history",
                         send_at=now + timedelta(days=1), read=False),
        ]
        # Older and reevaluated plans may have reminders without a schedule link.
        pending = Notification(user_id=user_id, kind="reminder", message="Upcoming session",
                               send_at=now + timedelta(days=1), read=False)
        db.add_all([*preserved, pending])
        db.commit()
        preserved_ids = {item.id for item in preserved}
        pending_id = pending.id
        schedule_ids = set(db.scalars(select(ScheduledSession.id).where(
            ScheduledSession.plan_id == plans[0],
        )))
    bob_before = client.get("/api/notifications", headers=bob).json()

    response = client.post("/api/assessments", headers=alice, json=referral)
    assert response.status_code == 201, response.text
    notifications = client.get("/api/notifications", headers=alice).json()
    assert preserved_ids <= {item["id"] for item in notifications}
    assert pending_id not in {item["id"] for item in notifications}
    assert client.get("/api/notifications", headers=bob).json() == bob_before
    assert logged.json()["id"] in {item["id"] for item in client.get("/api/sessions", headers=alice).json()}
    with SessionLocal() as db:
        assert db.scalar(select(Notification.id).where(
            Notification.user_id == user_id, Notification.kind == "reminder",
            Notification.read.is_(False), Notification.send_at >= now,
        )) is None
        assert set(db.scalars(select(ScheduledSession.id).where(
            ScheduledSession.plan_id == plans[0],
        ))) == schedule_ids


def test_in_scope_reassessment_keeps_current_plan(client, make_user):
    headers = make_user()
    intake = {"body_region": "knee", "pain_level": 3}
    assert client.post("/api/assessments", headers=headers, json=intake).status_code == 201
    plan = client.post("/api/plans", headers=headers).json()
    reminders = client.get("/api/notifications", headers=headers).json()
    assert client.post("/api/assessments", headers=headers, json=intake).status_code == 201
    current = client.get("/api/plans/current", headers=headers)
    assert current.status_code == 200
    assert current.json()["id"] == plan["id"]
    assert client.get("/api/notifications", headers=headers).json() == reminders

