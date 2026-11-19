"""Summary measurements only; never camera frames or landmark coordinates."""
from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class MovementMeasurement(TimestampMixin, Base):
    __tablename__ = "movement_measurements"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("exercise_sessions.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"))
    protocol: Mapped[str] = mapped_column(String(40))
    side: Mapped[str] = mapped_column(String(5))
    reps: Mapped[int] = mapped_column(Integer)
    partials: Mapped[int] = mapped_column(Integer)
    target_reps: Mapped[int] = mapped_column(Integer)
    hold_seconds: Mapped[float] = mapped_column(Float)
    min_angle: Mapped[float] = mapped_column(Float)
    max_angle: Mapped[float] = mapped_column(Float)
    tracking_ratio: Mapped[float] = mapped_column(Float)
    duration_seconds: Mapped[float] = mapped_column(Float)
