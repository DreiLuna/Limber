"""Persist per-exercise camera summaries linked to normal session safety checks."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "movement_measurements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("exercise_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_id", sa.String(120), sa.ForeignKey("exercises.id"), nullable=False),
        sa.Column("protocol", sa.String(40), nullable=False),
        sa.Column("side", sa.String(5), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("partials", sa.Integer(), nullable=False),
        sa.Column("target_reps", sa.Integer(), nullable=False),
        sa.Column("hold_seconds", sa.Float(), nullable=False),
        sa.Column("min_angle", sa.Float(), nullable=False),
        sa.Column("max_angle", sa.Float(), nullable=False),
        sa.Column("tracking_ratio", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_movement_measurements_user_id", "movement_measurements", ["user_id"])
    op.create_index("ix_movement_measurements_session_id", "movement_measurements", ["session_id"])


def downgrade():
    op.drop_table("movement_measurements")
