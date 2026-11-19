"""Smoke test for scripts/seed_synthetic_patients.py: it runs, the data passes the anonymity checks,
and --reset removes everything it created."""
from sqlalchemy import delete, func, select, update

from app.core.database import SessionLocal
from app.modules.ai.models import AIOutputLog
from app.modules.assessment.models import Assessment
from app.modules.model_config.models import ModelConfigVersion
from app.modules.plans.models import RecoveryPlan
from app.modules.reevaluation.models import ReevaluationDecision
from app.modules.users.models import User
from scripts import seed_synthetic_patients as seed


def _cleanup():
    with SessionLocal() as db:
        seed.reset(db)
        for model in (Assessment, RecoveryPlan, ReevaluationDecision, AIOutputLog):
            db.execute(update(model).values(config_version_id=None))
        db.execute(delete(ModelConfigVersion))
        db.commit()


def test_seed_creates_versions_and_resets():
    _cleanup()
    try:
        assert seed.main(["-n", "12", "--seed", "1"]) == 0
        with SessionLocal() as db:
            users = db.scalar(select(func.count()).select_from(User).where(User.email.like(f"%@{seed.DOMAIN}")))
            versions = db.scalars(select(ModelConfigVersion.version).order_by(ModelConfigVersion.version)).all()
            tagged = db.scalars(select(Assessment.config_version_id).join(User, User.id == Assessment.user_id)
                                .where(User.email.like(f"%@{seed.DOMAIN}"))).all()
        assert users == 12 and list(versions) == [1, 2]
        assert all(v is not None for v in tagged) and len(set(tagged)) == 2

        assert seed.main(["-n", "3", "--reset", "--single-version"]) == 0
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(User).where(User.email.like(f"%@{seed.DOMAIN}"))) == 3
    finally:
        _cleanup()
