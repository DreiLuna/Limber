from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class ReevaluationDecision(TimestampMixin, Base):
    __tablename__ = "reevaluation_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("recovery_plans.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(20))
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
