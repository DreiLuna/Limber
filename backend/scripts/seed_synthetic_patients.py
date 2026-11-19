"""Fill the database with synthetic patients so the clinician dashboard has something to show.

Every record is made up. Accounts use the reserved example.com domain and can't sign in
(their password hash is not a real hash). Run after migrations and the catalog load:

    python -m scripts.seed_synthetic_patients                 # 40 patients over the last 10 weeks
    python -m scripts.seed_synthetic_patients -n 80 --seed 7
    python -m scripts.seed_synthetic_patients --reset         # delete earlier synthetic patients first

By default the first half of the timeline is recorded under config v1, then a v2 is created
(slightly stricter scope, edited prompt) and the second half is recorded under it, so the
"By config version" table has something to compare. Pass --single-version to skip that.
"""
import argparse
import random
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import delete, select

import app.models  # noqa: F401  (registers every table)
from app.core.database import SessionLocal
from app.core.vocab import ActivityDifficulty, Limitation
from app.modules.ai.models import AIOutputLog
from app.modules.assessment.eligibility import EligibilityService
from app.modules.assessment.models import Assessment
from app.modules.catalog.models import Exercise
from app.modules.model_config.models import ModelConfigVersion
from app.modules.model_config.service import create_version, ensure_seed_version, get_active_config
from app.modules.notifications.models import Notification
from app.modules.plans.models import PlanItem, RecoveryPlan, ScheduledSession
from app.modules.plans.scheduling import build_schedule
from app.modules.progress.models import ProgressRecord
from app.modules.recommendation.filtering import build_fallback_plan
from app.modules.reevaluation.models import ReevaluationDecision
from app.modules.sessions.models import ExerciseSession
from app.modules.users.models import User

DOMAIN = "synthetic.example.com"
REGIONS = ["lower_back", "lower_back", "knee", "knee", "shoulder", "ankle"]  # rough real-world mix
AI_ERRORS = ["not_eligible:made_up_exercise", "sets_out_of_range:x:9", "reps_out_of_range:x:40",
             "count:3 not in [4,6]", "client_error:TimeoutError", "schema:('exercises',):Field required"]


def at(day: date, hour: int = 10) -> datetime:
    return datetime.combine(day, time(hour), tzinfo=UTC)


def reset(db) -> int:
    """Delete synthetic patients child-first (SQLite doesn't enforce ON DELETE CASCADE by default)."""
    ids = list(db.scalars(select(User.id).where(User.email.like(f"%@{DOMAIN}"))))
    if not ids:
        return 0
    plan_ids = list(db.scalars(select(RecoveryPlan.id).where(RecoveryPlan.user_id.in_(ids))))
    db.execute(delete(PlanItem).where(PlanItem.plan_id.in_(plan_ids)))
    for model in (Notification, ExerciseSession, ProgressRecord, ReevaluationDecision, AIOutputLog,
                  ScheduledSession, RecoveryPlan, Assessment):
        db.execute(delete(model).where(model.user_id.in_(ids)))
    db.execute(delete(User).where(User.id.in_(ids)))
    db.commit()
    return len(ids)


def make_patient(db, rng: random.Random, i: int, intake_day: date, today: date, config, catalog) -> None:
    user = User(email=f"patient{i:03d}@{DOMAIN}", password_hash="!synthetic", display_name="")
    db.add(user)
    db.flush()

    region = rng.choice(REGIONS)
    pain = min(10, max(1, round(rng.gauss(4.6, 1.6))))
    red_flags = ["numbness"] if rng.random() < 0.06 else []
    limitations = rng.sample([x.value for x in Limitation], k=rng.choice([0, 0, 1, 2]))
    activities = rng.sample([x.value for x in ActivityDifficulty], k=rng.choice([1, 2, 3]))
    t = config.thresholds
    scope = EligibilityService(t).evaluate(
        Assessment(body_region=region, pain_level=pain, limitations=limitations, red_flags=red_flags),
        catalog,
    )
    a = Assessment(
        user_id=user.id, body_region=region, pain_level=pain, limitations=limitations,
        activity_difficulties=activities, red_flags=red_flags, in_scope=scope.scope.in_scope,
        referral_reasons=scope.scope.referral_reasons, starting_difficulty=scope.scope.starting_difficulty,
        created_at=at(intake_day, 9), config_version_id=config.id,
    )
    db.add(a)
    db.flush()
    if not scope.can_generate_plan:
        return

    # AI planner call: ~78% valid, otherwise a validation error or timeout and the rule-based plan.
    ai_ok = rng.random() < 0.78
    errors = [] if ai_ok else rng.sample(AI_ERRORS, k=rng.choice([1, 1, 2]))
    latency = int(rng.lognormvariate(7.3, 0.35)) if "client_error:TimeoutError" not in errors else 5000
    db.add(AIOutputLog(user_id=user.id, task="plan", request={"assessment_id": a.id}, response=None,
                       valid=ai_ok, errors=errors, used_fallback=not ai_ok, latency_ms=latency,
                       created_at=at(intake_day, 9), config_version_id=config.id))

    items = build_fallback_plan(scope.exercises, activities, t)
    freq = t["plan"]["default_frequency_per_week"]
    weeks_total = t["reevaluation"]["reassess_after_weeks"]
    plan = RecoveryPlan(user_id=user.id, assessment_id=a.id, status="active", source="ai" if ai_ok else "fallback",
                        difficulty_level=scope.scope.starting_difficulty, frequency_per_week=freq,
                        start_date=intake_day, created_at=at(intake_day, 9), config_version_id=config.id)
    plan.items = [PlanItem(exercise_id=x.exercise_id, position=n, sets=x.sets, reps=x.reps)
                  for n, x in enumerate(items)]
    plan.schedule = [ScheduledSession(user_id=user.id, scheduled_date=d, week_index=w)
                     for d, w in build_schedule(intake_day, freq, weeks_total)]
    db.add(plan)
    db.flush()

    # Patient trajectory: most improve, some plateau, a few get worse.
    kind = rng.choices(["improve", "plateau", "worse"], weights=[70, 20, 10])[0]
    slope = {"improve": -rng.uniform(0.4, 0.9), "plateau": rng.uniform(-0.15, 0.15),
             "worse": rng.uniform(0.5, 1.0)}[kind]
    adherence = rng.uniform(0.45, 1.0)
    prev_avg = None
    for week in range(weeks_total):
        week_start = intake_day + timedelta(days=7 * week)
        if week_start + timedelta(days=7) > today:
            break
        sessions = [s for s in plan.schedule if s.week_index == week]
        done, pains, max_pain = 0, [], 0
        for s in sessions:
            if rng.random() > adherence:
                continue
            base = pain + slope * (week + 0.5)
            before = min(10, max(0, round(base + rng.gauss(0, 0.8))))
            after = min(10, max(0, round(before + rng.gauss(-0.6, 0.7))))
            db.add(ExerciseSession(user_id=user.id, plan_id=plan.id, scheduled_session_id=s.id,
                                   performed_at=at(s.scheduled_date, 18), completed=True, pain_before=before,
                                   pain_after=after, perceived_difficulty=rng.randint(2, 4)))
            done += 1
            pains.append(after)
            max_pain = max(max_pain, before, after)
        rate = done / len(sessions) if sessions else 0
        avg = round(sum(pains) / len(pains), 2) if pains else None
        db.add(ProgressRecord(user_id=user.id, plan_id=plan.id, week_index=week, week_start=week_start,
                              completion_rate=round(rate, 2), avg_post_pain=avg, max_session_pain=max_pain or None,
                              pain_change=None if avg is None or prev_avg is None else round(avg - prev_avg, 2),
                              missed_sessions=len(sessions) - done, created_at=at(week_start + timedelta(days=7), 8)))

        r = t["reevaluation"]
        if max_pain >= r["referral_session_pain"]:
            action, reasons = "refer", [f"session_pain_{max_pain}"]
        elif avg is not None and prev_avg is not None and avg - prev_avg >= r["reduce_avg_pain_rise_one_week"]:
            action, reasons = "reduce", [f"avg_pain_rose_{avg - prev_avg:g}_in_one_week"]
        elif rate < r["reduce_completion_below"]:
            action, reasons = "reduce", [f"completion_{rate:g}"]
        elif rate >= r["increase_completion_at_least"] and week >= r["increase_stable_weeks"] - 1 and kind == "improve":
            action, reasons = "increase", [f"completion_{rate:g}"]
        else:
            action, reasons = "continue", []
        db.add(ReevaluationDecision(user_id=user.id, plan_id=plan.id, action=action, reasons=reasons,
                                    created_at=at(week_start + timedelta(days=7), 8), config_version_id=config.id))
        prev_avg = avg if avg is not None else prev_avg
        if action == "refer":
            plan.status = "referred"
            break
        if action == "increase":
            plan.difficulty_level = min(3, plan.difficulty_level + 1)
    else:
        if (today - intake_day).days >= 7 * weeks_total:
            db.add(ReevaluationDecision(user_id=user.id, plan_id=plan.id, action="reassess",
                                        reasons=[f"plan_complete_after_{weeks_total}_weeks"],
                                        created_at=at(intake_day + timedelta(days=7 * weeks_total), 8),
                                        config_version_id=config.id))
            plan.status = "reassessment_required"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", type=int, default=40, help="number of synthetic patients")
    ap.add_argument("--weeks", type=int, default=10, help="spread intakes over this many past weeks")
    ap.add_argument("--seed", type=int, default=5030)
    ap.add_argument("--reset", action="store_true", help="delete earlier synthetic patients first")
    ap.add_argument("--single-version", action="store_true", help="record everything under the active version")
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    today = date.today()
    with SessionLocal() as db:
        if args.reset:
            print(f"Removed {reset(db)} synthetic patients")
        catalog = list(db.scalars(select(Exercise)))
        if not catalog:
            print("The exercise catalog is empty; run `python -m scripts.import_catalog --load-only` first.")
            return 1
        ensure_seed_version(db)
        v_first = get_active_config(db)
        days = sorted(today - timedelta(days=rng.randint(0, 7 * args.weeks)) for _ in range(args.n))
        switch_at = len(days) // 2 if not args.single_version else len(days)
        config = v_first
        for i, day in enumerate(days):
            if i == switch_at:
                t = dict(v_first.thresholds)
                t["scope"] = {**t["scope"], "max_starting_pain": 5}
                create_version(
                    db, thresholds=t, author_id=None, activate=True,
                    prompt_instructions=v_first.prompt_instructions
                    + "\n- Favor exercises that can be done standing when the user has floor limitations.",
                    note="Synthetic demo: refer pain 6 intakes and prefer standing exercises",
                )
                config = get_active_config(db)
            make_patient(db, rng, i, day, today, config, catalog)
            db.commit()
        versions = db.scalars(select(ModelConfigVersion.version).order_by(ModelConfigVersion.version)).all()
    print(f"Created {args.n} synthetic patients; config versions now {list(versions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
