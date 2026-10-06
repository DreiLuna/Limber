from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Exercise(Base):
    """An approved exercise. Rows come only from scripts/import_catalog.py, never from the AI."""
    __tablename__ = "exercises"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)  # free-exercise-db id
    name: Mapped[str] = mapped_column(String(200))
    body_regions: Mapped[list[str]] = mapped_column(JSON)
    difficulty: Mapped[int] = mapped_column(Integer)  # 1-3
    category: Mapped[str] = mapped_column(String(30))
    equipment: Mapped[str | None] = mapped_column(String(50))
    instructions: Mapped[list[str]] = mapped_column(JSON, default=list)
    sets_min: Mapped[int] = mapped_column(Integer)
    sets_max: Mapped[int] = mapped_column(Integer)
    reps_min: Mapped[int] = mapped_column(Integer)
    reps_max: Mapped[int] = mapped_column(Integer)
    media: Mapped[list[str]] = mapped_column(JSON, default=list)
    contraindications: Mapped[list[str]] = mapped_column(JSON, default=list)
    targets_activities: Mapped[list[str]] = mapped_column(JSON, default=list)
