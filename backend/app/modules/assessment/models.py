from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class Assessment(TimestampMixin, Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    body_region: Mapped[str] = mapped_column(String(30))
    pain_level: Mapped[int] = mapped_column(Integer)  # 0-10
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    activity_difficulties: Mapped[list[str]] = mapped_column(JSON, default=list)
    red_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    description: Mapped[str | None] = mapped_column(Text)
    # Result of the deterministic scope check
    in_scope: Mapped[bool] = mapped_column(Boolean)
    referral_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    starting_difficulty: Mapped[int | None] = mapped_column(Integer)
