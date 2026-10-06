"""End-to-end API checks: auth, intake routing, fallback plan, and access control."""


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_register_login_me(client):
    client.post("/api/auth/register", json={"email": "a@b.com", "password": "password123"})
    r = client.post("/api/auth/login", data={"username": "a@b.com", "password": "password123"})
    assert r.status_code == 200
    me = client.get("/api/users/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email"] == "a@b.com" and me.json()["subscription_status"] == "trial"


def test_wrong_password(client):
    client.post("/api/auth/register", json={"email": "c@d.com", "password": "password123"})
    assert client.post("/api/auth/login", data={"username": "c@d.com", "password": "nope"}).status_code == 401


def test_duplicate_email(client):
    body = {"email": "dup@x.com", "password": "password123"}
    client.post("/api/auth/register", json=body)
    assert client.post("/api/auth/register", json=body).status_code == 409


def test_requires_auth(client):
    for path in ("/api/users/me", "/api/assessments/latest", "/api/plans/current"):
        assert client.get(path).status_code == 401


def test_out_of_scope_intake_blocks_plan(client, make_user):
    h = make_user()
    a = client.post("/api/assessments", headers=h, json={"body_region": "knee", "pain_level": 8})
    assert a.status_code == 201 and a.json()["in_scope"] is False
    r = client.post("/api/plans", headers=h)
    assert r.status_code == 409 and "pain_too_high:8" in r.json()["detail"]["referral_reasons"]


def test_in_scope_intake_creates_fallback_plan(client, make_user):
    h = make_user()
    a = client.post("/api/assessments", headers=h, json={
        "body_region": "lower_back", "pain_level": 5,
        "limitations": ["cannot_kneel"], "activity_difficulties": ["bending", "sitting_long"],
    })
    assert a.json()["starting_difficulty"] == 1
    r = client.post("/api/plans", headers=h)
    assert r.status_code == 201, r.text
    plan = r.json()
    assert plan["source"] == "fallback" and 4 <= len(plan["items"]) <= 6
    assert len(plan["schedule"]) == 3 * 4  # 3x/week for 4 weeks

    # every planned exercise is in region, at level 1, not contraindicated, within limits
    for item in plan["items"]:
        ex = client.get(f"/api/exercises/{item['exercise_id']}").json()
        assert "lower_back" in ex["body_regions"] and ex["difficulty"] == 1
        assert "cannot_kneel" not in ex["contraindications"]
        assert ex["sets_min"] <= item["sets"] <= ex["sets_max"]
        assert ex["reps_min"] <= item["reps"] <= ex["reps_max"]


def test_users_cannot_see_each_others_records(client, make_user):
    alice, bob = make_user(), make_user()
    client.post("/api/assessments", headers=alice, json={"body_region": "knee", "pain_level": 4})
    assert client.post("/api/plans", headers=alice).status_code == 201
    assert client.get("/api/plans/current", headers=bob).status_code == 404
    assert client.get("/api/assessments/latest", headers=bob).status_code == 404


def test_invalid_intake_values_rejected(client, make_user):
    h = make_user()
    assert client.post("/api/assessments", headers=h, json={"body_region": "knee", "pain_level": 11}).status_code == 422
    assert client.post("/api/assessments", headers=h, json={"body_region": "elbow", "pain_level": 3}).status_code == 422
