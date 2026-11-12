"""Track scheduled-session email reminder delivery."""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("scheduled_session_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_notifications_scheduled_session_id",
        "notifications",
        ["scheduled_session_id"],
    )
    op.create_index(
        "ix_notifications_email_reminder_queue",
        "notifications",
        ["kind", "send_at", "email_sent_at"],
    )

    bind = op.get_bind()
    scheduled_date = (
        "date(notifications.send_at)"
        if bind.dialect.name == "sqlite"
        else "CAST(notifications.send_at AS DATE)"
    )
    bind.exec_driver_sql(
        f"""
        UPDATE notifications
        SET scheduled_session_id = (
            SELECT scheduled_sessions.id
            FROM scheduled_sessions
            JOIN recovery_plans ON recovery_plans.id = scheduled_sessions.plan_id
            WHERE recovery_plans.status = 'active'
              AND scheduled_sessions.user_id = notifications.user_id
              AND scheduled_sessions.scheduled_date = {scheduled_date}
            ORDER BY scheduled_sessions.id DESC
            LIMIT 1
        )
        WHERE notifications.kind = 'reminder'
          AND notifications.scheduled_session_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_email_reminder_queue", table_name="notifications")
    op.drop_index("ix_notifications_scheduled_session_id", table_name="notifications")
    op.drop_column("notifications", "email_sent_at")
    op.drop_column("notifications", "scheduled_session_id")
