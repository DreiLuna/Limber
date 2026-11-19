from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.modules.users import models as _users  # noqa: F401  (author_id FK target must be registered)


class ModelConfigVersion(TimestampMixin, Base):
    """One saved version of the decision thresholds and the AI prompt instructions.

    Versions are append-only: editing creates a new row, rollback re-activates an old one.
    Exactly one row is active; new intakes, plans, decisions and AI calls record its id.
    """
    __tablename__ = "model_config_versions"
    __table_args__ = (
        Index("uq_model_config_one_active", "is_active", unique=True,
              postgresql_where=text("is_active"), sqlite_where=text("is_active")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    thresholds: Mapped[dict] = mapped_column(JSON)
    prompt_instructions: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(String(500), default="")
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    parent_version: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
