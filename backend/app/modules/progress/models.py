from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class ProgressRecord(TimestampMixin, Base):
    """One row per plan week. Computed by progress.metrics, never by the AI."""
    __tablename__ = "progress_records"
    __table_args__ = (UniqueConstraint("plan_id", "week_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("recovery_plans.id", ondelete="CASCADE"))
    week_index: Mapped[int] = mapped_column(Integer)
    week_start: Mapped[date] = mapped_column(Date)
    completion_rate: Mapped[float] = mapped_column(Float)
    avg_post_pain: Mapped[float | None] = mapped_column(Float)
    max_session_pain: Mapped[int | None] = mapped_column(Integer)
    pain_change: Mapped[float | None] = mapped_column(Float)
    missed_sessions: Mapped[int] = mapped_column(Integer)
