from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, utcnow


class ExerciseSession(TimestampMixin, Base):
    __tablename__ = "exercise_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("recovery_plans.id", ondelete="CASCADE"), index=True)
    scheduled_session_id: Mapped[int | None] = mapped_column(ForeignKey("scheduled_sessions.id"))
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed: Mapped[bool] = mapped_column(Boolean)
    pain_before: Mapped[int] = mapped_column(Integer)
    pain_after: Mapped[int] = mapped_column(Integer)
    perceived_difficulty: Mapped[int] = mapped_column(Integer)  # 1 (too easy) - 5 (too hard)
    too_difficult_exercise_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text)


class PainReport(TimestampMixin, Base):
    """Pain reported outside a session, including new red-flag symptoms."""
    __tablename__ = "pain_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("exercise_sessions.id"))
    pain_level: Mapped[int] = mapped_column(Integer)
    red_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
