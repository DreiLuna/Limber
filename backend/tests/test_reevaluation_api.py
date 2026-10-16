"""Reevaluation decisions, persisted plan effects, safety priority and repeat calls."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.modules.assessment.models import Assessment
from app.modules.notifications.models import Notification
from app.modules.plans.models import RecoveryPlan, ScheduledSession
from app.modules.plans.scheduling import build_schedule
from app.modules.reevaluation.models import ReevaluationDecision
from app.modules.sessions.models import ExerciseSession, PainReport

NOW = datetime(2026, 11, 20, 12, tzinfo=UTC)


@pytest.fixture
def seed(client, make_user, monkeypatch):
    monkeypatch.setattr("app.modules.reevaluation.service.utcnow", lambda: NOW)
    monkeypatch.setattr("app.modules.sessions.router.utcnow", lambda: NOW)

    def make(weeks=(), level=1, region="knee", limitations=None):
        headers = make_user()
        assessment = client.post("/api/assessments", headers=headers, json={
            "body_region": region, "pain_level": 5, "limitations": limitations or [],
        }).json()
        response = client.post("/api/plans", headers=headers)
        assert response.status_code == 201, response.text
        plan_id = response.json()["id"]
        start = NOW.date() - timedelta(weeks=len(weeks))
        with SessionLocal() as db:
            plan = db.get(RecoveryPlan, plan_id)
            plan.start_date, plan.difficulty_level = start, level
            db.get(Assessment, assessment["id"]).created_at = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
            db.execute(delete(ScheduledSession).where(ScheduledSession.plan_id == plan_id))
            db.execute(delete(Notification).where(Notification.user_id == plan.user_id))
            for day, index in build_schedule(start, 3, max(len(weeks) + 2, 4)):
                scheduled = ScheduledSession(
                    plan_id=plan_id, user_id=plan.user_id, scheduled_date=day, week_index=index,
                )
                db.add(scheduled)
                db.flush()
                if index < len(weeks):
                    count, pain = weeks[index]
                    # First count of the three scheduled sessions are completed.
                    if (day - start).days % 7 in (0, 2, 4)[:count]:
                        db.add(ExerciseSession(
                            user_id=plan.user_id, plan_id=plan_id, scheduled_session_id=scheduled.id,
                            performed_at=datetime.combine(day, datetime.min.time(), tzinfo=UTC), completed=True,
                            pain_before=pain, pain_after=pain, perceived_difficulty=3,
                        ))
            db.commit()
        return headers, plan_id
    return make


def test_auth_and_no_plan(client, make_user):
    assert client.post("/api/reevaluations").status_code == 401
    assert client.post("/api/reevaluations", headers=make_user()).status_code == 404


def test_partial_week_continues_and_is_idempotent(client, seed):
    headers, plan_id = seed()
    for _ in range(2):
        result = client.post("/api/reevaluations", headers=headers)
        assert result.status_code == 200 and result.json()["action"] == "continue"
    with SessionLocal() as db:
        assert len(list(db.scalars(select(ReevaluationDecision).where(ReevaluationDecision.plan_id == plan_id)))) == 1


@pytest.mark.parametrize("weeks", [[(1, 3)], [(3, 3), (3, 4)]])
def test_reduce_frequency_once_preserves_history(client, seed, weeks):
    headers, plan_id = seed(weeks)
    before = client.get("/api/plans/current", headers=headers).json()
    past = {s["id"] for s in before["schedule"] if s["scheduled_date"] <= NOW.date().isoformat()}
    for _ in range(2):
        result = client.post("/api/reevaluations", headers=headers)
        assert result.json()["action"] == "reduce"
    after = client.get("/api/plans/current", headers=headers).json()
    assert after["frequency_per_week"] == 2 and after["difficulty_level"] == 1
    assert past <= {s["id"] for s in after["schedule"]}
    assert len({s["scheduled_date"] for s in after["schedule"]}) == len(after["schedule"])
    assert len(client.get("/api/sessions", headers=headers).json()) == sum(done for done, _ in weeks)
    with SessionLocal() as db:
        assert db.get(RecoveryPlan, plan_id).status == "active"


def test_increase_uses_eligible_exercises_and_catalog_doses(client, seed):
    headers, _ = seed([(3, 3), (3, 3)], limitations=["cannot_kneel"])
    for _ in range(2):
        assert client.post("/api/reevaluations", headers=headers).json()["action"] == "increase"
    plan = client.get("/api/plans/current", headers=headers).json()
    assert plan["difficulty_level"] == 2 and plan["source"] == "fallback"
    assert 4 <= len(plan["items"]) <= 6
    for item in plan["items"]:
        exercise = client.get(f"/api/exercises/{item['exercise_id']}").json()
        assert "knee" in exercise["body_regions"] and exercise["difficulty"] == 2
        assert "cannot_kneel" not in exercise["contraindications"]
        assert exercise["sets_min"] <= item["sets"] <= exercise["sets_max"]
        assert exercise["reps_min"] <= item["reps"] <= exercise["reps_max"]


@pytest.mark.parametrize("weeks,action", [
    ([(2, 3)] * 4, "reassess"),
    ([(2, 5)] * 6, "refer"),
    ([(3, 3), (3, 4), (3, 5)], "refer"),
])
def test_terminal_actions_stop_plan_and_require_new_intake(client, seed, weeks, action):
    headers, plan_id = seed(weeks)
    for _ in range(2):
        result = client.post("/api/reevaluations", headers=headers)
        assert result.status_code == 200 and result.json()["action"] == action
    assert client.get("/api/plans/current", headers=headers).status_code == 404
    assert client.post("/api/plans", headers=headers).status_code == 409
    with SessionLocal() as db:
        assert db.get(RecoveryPlan, plan_id).status == ("referred" if action == "refer" else "reassessment_required")
    # A fresh intake is required, rather than regenerating from the stopped assessment.
    client.post("/api/assessments", headers=headers, json={"body_region": "knee", "pain_level": 5})
    assert client.post("/api/plans", headers=headers).status_code == 201


@pytest.mark.parametrize("before,after,flags", [(8, 3, []), (3, 8, []), (3, 3, ["numbness"])])
def test_logging_urgent_data_automatically_refers_even_after_continue(client, seed, before, after, flags):
    headers, plan_id = seed()
    assert client.post("/api/reevaluations", headers=headers).json()["action"] == "continue"
    logged = client.post("/api/sessions", headers=headers, json={
        "completed": True, "pain_before": before, "pain_after": after,
        "perceived_difficulty": 3, "new_red_flags": flags,
    })
    assert logged.status_code == 201, logged.text
    assert client.get("/api/plans/current", headers=headers).status_code == 404
    assert client.post("/api/reevaluations", headers=headers).json()["action"] == "refer"
    assert client.post("/api/sessions", headers=headers, json={
        "completed": True, "pain_before": 3, "pain_after": 3, "perceived_difficulty": 3,
    }).status_code == 409
    with SessionLocal() as db:
        assert db.get(RecoveryPlan, plan_id).status == "referred"
        assert len(list(db.scalars(select(PainReport).where(PainReport.session_id == logged.json()["id"])))) == 1


def test_missing_next_level_catalog_requests_reassessment(client, seed, monkeypatch, t):
    headers, _ = seed([(3, 3), (3, 3)])
    monkeypatch.setitem(t["plan"], "min_exercises", 100_000)
    result = client.post("/api/reevaluations", headers=headers)
    assert result.json()["action"] == "reassess"
    assert result.json()["reasons"] == ["insufficient_eligible_exercises_for_increase"]
    assert client.get("/api/plans/current", headers=headers).status_code == 404


def test_another_users_warning_does_not_affect_this_plan(client, seed):
    alice, _ = seed()
    bob, _ = seed()
    client.post("/api/sessions", headers=alice, json={
        "completed": True, "pain_before": 3, "pain_after": 8, "perceived_difficulty": 3,
    })
    result = client.post("/api/reevaluations", headers=bob)
    assert result.json()["action"] == "continue"
    assert client.get("/api/plans/current", headers=bob).status_code == 200


def test_session_save_automatically_applies_weekly_reduction(client, seed):
    headers, plan_id = seed([(1, 3)])
    saved = client.post("/api/sessions", headers=headers, json={
        "completed": True, "pain_before": 3, "pain_after": 3, "perceived_difficulty": 3,
    })
    assert saved.status_code == 201
    plan = client.get("/api/plans/current", headers=headers).json()
    assert plan["frequency_per_week"] == 2
    with SessionLocal() as db:
        decision = db.scalar(select(ReevaluationDecision).where(ReevaluationDecision.plan_id == plan_id))
        assert decision.action == "reduce"
    notices = client.get("/api/notifications", headers=headers).json()
    assert any(notice["kind"] == "plan_update" for notice in notices)
    future_dates = {item["scheduled_date"] for item in plan["schedule"]
                    if item["scheduled_date"] > NOW.date().isoformat()}
    reminders = [notice for notice in notices if notice["kind"] == "reminder"]
    assert {notice["send_at"][:10] for notice in reminders} == future_dates


def test_extra_sessions_do_not_turn_low_adherence_into_increase(client, seed):
    headers, plan_id = seed([(1, 3), (1, 3)])
    with SessionLocal() as db:
        plan = db.get(RecoveryPlan, plan_id)
        for week in range(2):
            for _ in range(5):
                db.add(ExerciseSession(
                    user_id=plan.user_id, plan_id=plan_id, completed=True,
                    performed_at=NOW - timedelta(weeks=2-week),
                    pain_before=3, pain_after=3, perceived_difficulty=3,
                ))
        db.commit()
    assert client.post("/api/reevaluations", headers=headers).json()["action"] == "reduce"


def test_reduce_never_goes_below_one_session_per_week(client, seed):
    headers, plan_id = seed([(1, 3)])
    with SessionLocal() as db:
        db.get(RecoveryPlan, plan_id).frequency_per_week = 1
        db.commit()
    result = client.post("/api/reevaluations", headers=headers).json()
    assert result["action"] == "reduce" and "already_at_minimum_frequency" in result["reasons"]
    assert client.get("/api/plans/current", headers=headers).json()["frequency_per_week"] == 1


def test_maximum_difficulty_does_not_increase(client, seed):
    headers, _ = seed([(3, 3), (3, 3)], level=3)
    assert client.post("/api/reevaluations", headers=headers).json()["action"] == "continue"
    assert client.get("/api/plans/current", headers=headers).json()["difficulty_level"] == 3
