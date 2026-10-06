import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

# Use a throwaway SQLite database for tests. Must be set before the app is imported.
_DB = Path(tempfile.gettempdir()) / "limber_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["JWT_SECRET"] = "test-secret-key-that-is-at-least-32-bytes"

from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.config import get_thresholds  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.catalog.models import Exercise  # noqa: E402

CATALOG = Path(__file__).resolve().parents[1] / "data" / "catalog.json"


@dataclass
class Ex:
    """Lightweight exercise for pure rule tests (matches recommendation.ExerciseLike)."""
    id: str
    body_regions: list[str]
    difficulty: int = 1
    contraindications: list[str] = field(default_factory=list)
    targets_activities: list[str] = field(default_factory=list)
    sets_min: int = 1
    sets_max: int = 3
    reps_min: int = 8
    reps_max: int = 12


@pytest.fixture
def t():
    return get_thresholds()


@pytest.fixture(scope="session", autouse=True)
def _database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for row in json.loads(CATALOG.read_text(encoding="utf-8")):
            db.add(Exercise(**row))
        db.commit()
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client():
    return TestClient(app)


_counter = iter(range(10_000))


@pytest.fixture
def make_user(client):
    def _make() -> dict[str, str]:
        email = f"user{next(_counter)}@example.com"
        r = client.post("/api/auth/register", json={"email": email, "password": "password123"})
        assert r.status_code == 201, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
    return _make
