from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class AIOutputLog(TimestampMixin, Base):
    """Every AI call and its validation result, so fallback rate can be measured."""
    __tablename__ = "ai_output_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task: Mapped[str] = mapped_column(String(30))  # intake, plan, adjustment, explanation
    request: Mapped[dict] = mapped_column(JSON)
    response: Mapped[dict | None] = mapped_column(JSON)
    valid: Mapped[bool] = mapped_column(Boolean)
    errors: Mapped[list[str]] = mapped_column(JSON, default=list)
    used_fallback: Mapped[bool] = mapped_column(Boolean)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
