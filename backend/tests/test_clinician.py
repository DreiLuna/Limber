"""Clinician dashboard: role gate, anonymization, and cohort analytics.

The analytics fixture writes its rows with 2020 dates and every query filters to 2020, so the
numbers are exact even though other tests share the same database.
"""
import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.modules.ai.models import AIOutputLog
from app.modules.assessment.models import Assessment
from app.modules.catalog.models import Exercise
from app.modules.clinician.anonymize import (
    day_offset,
    is_valid_code,
    pseudonym,
    reason_key,
    resolve_pseudonym,
)
from app.modules.plans.models import PlanItem, RecoveryPlan
from app.modules.progress.models import ProgressRecord
from app.modules.reevaluation.models import ReevaluationDecision
from app.modules.sessions.models import ExerciseSession
from app.modules.users.models import User

Y2020 = {"start": "2020-01-01", "end": "2020-12-31"}
ENDPOINTS = (
    "/api/clinician/overview", "/api/clinician/analytics/intake", "/api/clinician/analytics/outcomes",
    "/api/clinician/analytics/rules", "/api/clinician/analytics/ai", "/api/clinician/patients",
)
SECRET_TEXT = "my neighbour Dave hurt me"  # free text that must never reach a clinician


def ts(month: int, day: int) -> datetime:
    return datetime(2020, month, day, 12, tzinfo=UTC)


@pytest.fixture
def clinician(client):
    email = "pt-dashboard@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    if r.status_code == 409:
        r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    with SessionLocal() as db:
        db.scalar(select(User).where(User.email == email)).role = "clinician"
        db.commit()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def cohort():
    """Three 2020 patients: knee (improving, AI plan), shoulder (out of scope), back (referred)."""
    with SessionLocal() as db:
        ex_id = db.scalars(select(Exercise.id)).first()
        users = [User(email=f"cohort{i}@example.com", password_hash="x", display_name=f"Cohort Person {i}")
                 for i in range(3)]
        db.add_all(users)
        db.flush()
        knee, shoulder, back = users

        a_knee = Assessment(user_id=knee.id, body_region="knee", pain_level=4, in_scope=True,
                            starting_difficulty=2, description=SECRET_TEXT, created_at=ts(3, 2),
                            limitations=["cannot_kneel"], activity_difficulties=["stairs"])
        a_sh = Assessment(user_id=shoulder.id, body_region="shoulder", pain_level=8, in_scope=False,
                          referral_reasons=["pain_too_high:8", "red_flag:numbness"], red_flags=["numbness"],
                          created_at=ts(3, 4))
        a_back = Assessment(user_id=back.id, body_region="lower_back", pain_level=5, in_scope=True,
                            starting_difficulty=1, created_at=ts(3, 10))
        db.add_all([a_knee, a_sh, a_back])
        db.flush()

        p_knee = RecoveryPlan(user_id=knee.id, assessment_id=a_knee.id, status="active", difficulty_level=2,
                              frequency_per_week=3, source="ai", start_date=date(2020, 3, 2), created_at=ts(3, 2))
        p_back = RecoveryPlan(user_id=back.id, assessment_id=a_back.id, status="referred", difficulty_level=1,
                              frequency_per_week=3, source="fallback", start_date=date(2020, 3, 10),
                              created_at=ts(3, 10))
        db.add_all([p_knee, p_back])
        db.flush()
        db.add(PlanItem(plan_id=p_knee.id, exercise_id=ex_id, position=0, sets=2, reps=10))

        db.add_all([
            ProgressRecord(user_id=knee.id, plan_id=p_knee.id, week_index=0, week_start=date(2020, 3, 2),
                           completion_rate=1.0, avg_post_pain=3.0, max_session_pain=4, pain_change=None,
                           missed_sessions=0, created_at=ts(3, 9)),
            ProgressRecord(user_id=knee.id, plan_id=p_knee.id, week_index=1, week_start=date(2020, 3, 9),
                           completion_rate=0.8, avg_post_pain=2.0, max_session_pain=3, pain_change=-1.0,
                           missed_sessions=1, created_at=ts(3, 16)),
            ProgressRecord(user_id=back.id, plan_id=p_back.id, week_index=0, week_start=date(2020, 3, 10),
                           completion_rate=0.6, avg_post_pain=6.0, max_session_pain=8, pain_change=None,
                           missed_sessions=1, created_at=ts(3, 17)),
        ])
        db.add(ExerciseSession(user_id=knee.id, plan_id=p_knee.id, performed_at=ts(3, 5), completed=True,
                               pain_before=4, pain_after=3, perceived_difficulty=3, notes=SECRET_TEXT))
        db.add_all([
            ReevaluationDecision(user_id=knee.id, plan_id=p_knee.id, action="continue", reasons=[],
                                 created_at=ts(3, 9)),
            ReevaluationDecision(user_id=knee.id, plan_id=p_knee.id, action="increase",
                                 reasons=["completion_0.8"], created_at=ts(3, 16)),
            ReevaluationDecision(user_id=back.id, plan_id=p_back.id, action="refer",
                                 reasons=["session_pain_8"], created_at=ts(3, 17)),
        ])
        db.add_all([
            AIOutputLog(user_id=knee.id, task="plan", request={"assessment_id": a_knee.id},
                        response={"secret": SECRET_TEXT}, valid=True, errors=[], used_fallback=False,
                        latency_ms=100, created_at=ts(3, 2)),
            AIOutputLog(user_id=back.id, task="plan", request={"assessment_id": a_back.id}, response=None,
                        valid=False, errors=["not_eligible:abc", "sets_out_of_range:abc:9"],
                        used_fallback=True, latency_ms=300, created_at=ts(3, 10)),
        ])
        db.commit()
        return {"knee": knee.id, "shoulder": shoulder.id, "back": back.id,
                "emails": [u.email for u in users], "names": [u.display_name for u in users]}


# ---------- access control ----------

def test_clinician_routes_require_auth(client):
    for path in ENDPOINTS:
        assert client.get(path).status_code == 401


def test_patients_are_forbidden(client, make_user):
    h = make_user()
    for path in ENDPOINTS:
        assert client.get(path, headers=h).status_code == 403


def test_register_cannot_self_assign_clinician(client):
    r = client.post("/api/auth/register",
                    json={"email": "sneaky@example.com", "password": "password123", "role": "clinician"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/users/me", headers=h).json()["role"] == "patient"
    assert client.get("/api/clinician/overview", headers=h).status_code == 403


def test_me_reports_clinician_role(client, clinician):
    assert client.get("/api/users/me", headers=clinician).json()["role"] == "clinician"


# ---------- anonymization helpers ----------

def test_pseudonym_is_stable_and_well_formed():
    assert pseudonym(42) == pseudonym(42) != pseudonym(43)
    assert is_valid_code(pseudonym(42)) and not is_valid_code("42") and not is_valid_code("P-zzzzzz")


@pytest.mark.parametrize("raw,key", [
    ("pain_too_high:8", "pain_too_high"),
    ("red_flag:numbness", "red_flag:numbness"),
    ("unsupported_region:neck", "unsupported_region:neck"),
    ("session_pain_8", "session_pain"),
    ("avg_pain_rose_2_over_two_weeks", "avg_pain_rose_over_two_weeks"),
    ("avg_pain_rose_1.5_in_one_week", "avg_pain_rose_in_one_week"),
    ("no_improvement_after_6_weeks", "no_improvement_after_weeks"),
    ("completion_0.4", "completion"),
    ("red_flag_reported", "red_flag_reported"),
    ("not_eligible:abc", "not_eligible"),
    ("client_error:TimeoutError", "client_error:TimeoutError"),
])
def test_reason_key(raw, key):
    assert reason_key(raw) == key


def test_day_offset():
    assert day_offset(ts(3, 9), ts(3, 2)) == 7
    assert day_offset(date(2020, 3, 2), ts(3, 2)) == 0
    assert day_offset(None, ts(3, 2)) is None


# ---------- analytics ----------

def test_intake_analytics(client, clinician, cohort):
    r = client.get("/api/clinician/analytics/intake", headers=clinician, params=Y2020).json()
    assert (r["total"], r["in_scope"], r["out_of_scope"]) == (3, 2, 1)
    assert r["in_scope_rate"] == pytest.approx(0.667)
    reasons = {c["key"]: c["count"] for c in r["out_of_scope_reasons"]}
    assert reasons == {"pain_too_high": 1, "red_flag:numbness": 1}
    assert {c["key"] for c in r["region_mix"]} == {"knee", "shoulder", "lower_back"}
    assert sum(w["intakes"] for w in r["weekly"]) == 3


def test_outcome_analytics(client, clinician, cohort):
    r = client.get("/api/clinician/analytics/outcomes", headers=clinician, params=Y2020).json()
    assert r["plans"] == 2 and r["active_plans"] == 1
    assert {c["key"]: c["count"] for c in r["plan_source_mix"]} == {"ai": 1, "fallback": 1}
    week0 = r["by_week"][0]
    assert week0["week_index"] == 0 and week0["n"] == 2 and week0["avg_post_pain"] == 4.5
    # knee: 4 -> 2 (drop 2), back: 5 -> 6 (drop -1); mean 0.5
    assert r["avg_pain_drop"] == 0.5
    knee = next(x for x in r["by_region"] if x["region"] == "knee")
    assert knee["avg_pain_drop"] == 2.0


def test_rule_analytics(client, clinician, cohort):
    r = client.get("/api/clinician/analytics/rules", headers=clinician, params=Y2020).json()
    actions = {c["key"]: c["count"] for c in r["action_counts"]}
    assert actions == {"continue": 1, "increase": 1, "refer": 1, "reduce": 0, "reassess": 0}
    assert {c["key"] for c in r["reason_counts"]} == {"completion", "session_pain"}
    assert (r["patients_evaluated"], r["patients_referred"], r["referral_rate"]) == (2, 1, 0.5)


def test_ai_analytics(client, clinician, cohort):
    r = client.get("/api/clinician/analytics/ai", headers=clinician, params=Y2020).json()
    assert (r["calls"], r["valid"], r["fallback"], r["fallback_rate"]) == (2, 1, 1, 0.5)
    assert r["latency_p50_ms"] == 200.0
    assert {c["key"]: c["count"] for c in r["error_counts"]} == {"not_eligible": 1, "sets_out_of_range": 1}


def test_region_filter(client, clinician, cohort):
    r = client.get("/api/clinician/analytics/ai", headers=clinician, params={**Y2020, "region": "knee"}).json()
    assert (r["calls"], r["fallback"]) == (1, 0)
    o = client.get("/api/clinician/overview", headers=clinician, params={**Y2020, "level": 1}).json()
    assert o["patients"] == 1 and o["referral_rate"] == 1.0


def test_bad_filters(client, clinician):
    assert client.get("/api/clinician/overview", headers=clinician,
                      params={"start": "2020-02-01", "end": "2020-01-01"}).status_code == 422
    assert client.get("/api/clinician/overview", headers=clinician, params={"region": "elbow"}).status_code == 422


# ---------- patients ----------

def test_patient_list_and_detail(client, clinician, cohort):
    rows = client.get("/api/clinician/patients", headers=clinician, params=Y2020).json()
    codes = {p["code"] for p in rows}
    assert codes == {pseudonym(cohort[k]) for k in ("knee", "shoulder", "back")}

    knee = next(p for p in rows if p["code"] == pseudonym(cohort["knee"]))
    assert knee["plan_status"] == "active" and knee["weeks_logged"] == 2 and knee["last_action"] == "increase"

    d = client.get(f"/api/clinician/patients/{knee['code']}", headers=clinician).json()
    assert d["assessments"][0]["day"] == 0 and d["plans"][0]["number"] == 1
    assert d["sessions"][0]["day"] == 3 and [x["day"] for x in d["decisions"]] == [7, 14]
    assert d["ai_logs"][0] == {"day": 0, "task": "plan", "valid": True, "used_fallback": False,
                               "errors": [], "latency_ms": 100}

    assert client.get("/api/clinician/patients/P-000000", headers=clinician).status_code == 404
    assert client.get("/api/clinician/patients/1", headers=clinician).status_code == 404


def test_clinicians_are_not_listed_as_patients(client, clinician):
    with SessionLocal() as db:
        pt = db.scalar(select(User).where(User.email == "pt-dashboard@example.com"))
        assert resolve_pseudonym(db, pseudonym(pt.id)) is None
    codes = {p["code"] for p in client.get("/api/clinician/patients", headers=clinician).json()}
    assert pseudonym(pt.id) not in codes


def test_no_identifying_data_in_any_response(client, clinician, cohort):
    bodies = [client.get(p, headers=clinician, params=Y2020).text for p in ENDPOINTS]
    bodies += [client.get(f"/api/clinician/patients/{pseudonym(cohort[k])}", headers=clinician).text
               for k in ("knee", "shoulder", "back")]
    for body in bodies:
        assert SECRET_TEXT not in body and "@example.com" not in body
        assert not any(name in body for name in cohort["names"])
        data = json.loads(body)
        assert not _has_key(data, {"user_id", "email", "display_name", "notes", "description", "id"})
        # Calendar dates only appear as cohort week buckets or the echoed filters.
        assert not [v for k, v in _strings(data) if k not in {"week_start", "start", "end"} and v[:4] == "2020"]


def _strings(obj, key=None):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v, key)
    elif isinstance(obj, str):
        yield key, obj


def _has_key(obj, keys) -> bool:
    if isinstance(obj, dict):
        return any(k in keys or _has_key(v, keys) for k, v in obj.items())
    if isinstance(obj, list):
        return any(_has_key(v, keys) for v in obj)
    return False
