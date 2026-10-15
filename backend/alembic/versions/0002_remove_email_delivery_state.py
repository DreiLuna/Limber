"""Remove unused external-delivery tracking from in-app notifications.

Revision ID: 0002
Revises: 0001
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("notifications", "sent_at")


def downgrade() -> None:
    import sqlalchemy as sa

    op.add_column("notifications", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
