from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100), default="")

    subscription: Mapped["Subscription | None"] = relationship(back_populates="user", uselist=False)


class Subscription(TimestampMixin, Base):
    """Stripe (test mode) subscription state. Card data never touches our database."""
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="trial")  # trial, active, canceled
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="subscription")
