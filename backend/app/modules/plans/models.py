from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class RecoveryPlan(TimestampMixin, Base):
    __tablename__ = "recovery_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, superseded, referred
    difficulty_level: Mapped[int] = mapped_column(Integer)
    frequency_per_week: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(20))  # "ai" or "fallback"
    start_date: Mapped[date] = mapped_column(Date)

    items: Mapped[list["PlanItem"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PlanItem.position"
    )
    schedule: Mapped[list["ScheduledSession"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="ScheduledSession.scheduled_date"
    )


class PlanItem(Base):
    __tablename__ = "plan_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("recovery_plans.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"))
    position: Mapped[int] = mapped_column(Integer)
    sets: Mapped[int] = mapped_column(Integer)
    reps: Mapped[int] = mapped_column(Integer)

    plan: Mapped[RecoveryPlan] = relationship(back_populates="items")


class ScheduledSession(Base):
    __tablename__ = "scheduled_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("recovery_plans.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scheduled_date: Mapped[date] = mapped_column(Date)
    week_index: Mapped[int] = mapped_column(Integer)  # 0-based week of the plan

    plan: Mapped[RecoveryPlan] = relationship(back_populates="schedule")
