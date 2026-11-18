"""End-to-end persistence, isolation, validation and safety priority."""
import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.modules.measurements.models import MovementMeasurement
from app.modules.sessions.models import ExerciseSession

pytest_plugins = ["tests.test_reevaluation_api"]


def summary(exercise="Seated_Knee_Extension", **changes):
    return dict(exercise_id=exercise, protocol="movement-v1", side="left", reps=5, partials=0,
                min_angle=90, max_angle=170, hold_seconds=3, duration_seconds=20,
                tracking_ratio=.95) | changes


def payload(**changes):
    return dict(completed=True, pain_before=2, pain_after=2, perceived_difficulty=3,
                measurements=[summary()]) | changes


def test_persist_reload_user_isolation_and_server_target(client, seed, make_user):
    headers, _ = seed()
    result = client.post("/api/sessions", headers=headers, json=payload())
    assert result.status_code == 201, result.text
    rows = client.get("/api/measurements", headers=headers).json()
    assert rows[0]["session_id"] == result.json()["id"]
    assert rows[0]["target_reps"] == 5
    assert rows[0]["reps"] == 5 and rows[0]["hold_seconds"] == 3
    assert client.get("/api/measurements", headers=make_user()).json() == []
    assert client.get("/api/measurements").status_code == 401


@pytest.mark.parametrize("measurements", [
    [summary(reps=-1)], [summary(reps=1.5)], [summary(reps=True)],
    [summary(min_angle=175, max_angle=90)], [summary(tracking_ratio=1.1)],
    [summary(hold_seconds=30)], [summary(duration_seconds=1)],
    [summary(protocol="unknown")], [summary(target_reps=1)],
    [summary("Bodyweight_Squat")], [summary(), summary()],
])
def test_invalid_or_unplanned_summary_is_atomic(client, seed, measurements):
    headers, plan_id = seed()
    result = client.post("/api/sessions", headers=headers, json=payload(measurements=measurements))
    assert result.status_code == 422, result.text
    with SessionLocal() as db:
        assert db.scalar(select(ExerciseSession).where(ExerciseSession.plan_id == plan_id)) is None
    assert client.get("/api/measurements", headers=headers).json() == []


def test_saved_measurement_cannot_bypass_referral(client, seed):
    headers, _ = seed()
    result = client.post("/api/sessions", headers=headers, json=payload(pain_after=8))
    assert result.status_code == 201
    assert client.get("/api/plans/current", headers=headers).status_code == 404
    assert len(client.get("/api/measurements", headers=headers).json()) == 1
    assert client.post("/api/sessions", headers=headers, json=payload()).status_code == 409


def test_self_reported_completion_alone_cannot_increase(client, seed):
    headers, _ = seed([(3, 3), (3, 3)])
    result = client.post("/api/reevaluations", headers=headers).json()
    assert result["action"] == "continue"
    assert result["reasons"] == ["measured_progress_requires_two_complete_weeks"]


@pytest.mark.parametrize("field,value,reason", [
    ("tracking_ratio", .5, "two_complete_weeks"),
    ("partials", 20, "two_complete_weeks"),
    ("reps", 0, "two_complete_weeks"),
    ("duration_seconds", 1, "two_complete_weeks"),
])
def test_poor_measurements_block_increase(client, seed, field, value, reason):
    headers, plan_id = seed([(3, 3), (3, 3)], measured=True)
    with SessionLocal() as db:
        rows = db.scalars(select(MovementMeasurement).join(ExerciseSession).where(
            ExerciseSession.plan_id == plan_id))
        for row in rows:
            setattr(row, field, value)
        db.commit()
    result = client.post("/api/reevaluations", headers=headers).json()
    assert result["action"] == "continue" and reason in result["reasons"][0]


def test_range_decline_and_side_mismatch_block_increase(client, seed):
    for field, value, reason in [("side", "right", "same_side"), ("min_angle", 120, "range_declined")]:
        headers, plan_id = seed([(3, 3), (3, 3)], measured=True)
        with SessionLocal() as db:
            rows = list(db.scalars(select(MovementMeasurement).join(ExerciseSession).where(
                ExerciseSession.plan_id == plan_id).order_by(ExerciseSession.performed_at)))
            for row in rows[len(rows)//2:]:
                setattr(row, field, value)
            db.commit()
        result = client.post("/api/reevaluations", headers=headers).json()
        assert result["action"] == "continue" and reason in result["reasons"][0]


def test_live_plan_creation_never_requests_ai(client, make_user, monkeypatch):
    def unavailable():
        pytest.fail("Final delivery must not call an AI provider")
    monkeypatch.setattr("app.modules.ai.planner.get_planner_client", unavailable)
    headers = make_user()
    client.post("/api/assessments", headers=headers, json={"body_region": "knee", "pain_level": 5})
    result = client.post("/api/plans", headers=headers)
    assert result.status_code == 201 and result.json()["source"] == "fallback"


@pytest.mark.parametrize("region,pain,exercise", [
    ("knee", 3, "Bodyweight_Squat"), ("knee", 5, "Seated_Knee_Extension"),
    ("shoulder", 5, "Wall_Press_Up"),
])
def test_all_three_camera_exercises_can_be_planned_and_saved(client, make_user, region, pain, exercise):
    headers = make_user()
    client.post("/api/assessments", headers=headers, json={"body_region": region, "pain_level": pain})
    plan = client.post("/api/plans", headers=headers).json()
    assert exercise in {item["exercise_id"] for item in plan["items"]}
    result = client.post("/api/sessions", headers=headers, json=payload(measurements=[summary(exercise)]))
    assert result.status_code == 201, result.text
    assert client.get("/api/measurements", headers=headers).json()[0]["exercise_id"] == exercise
