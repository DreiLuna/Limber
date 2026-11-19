"""Versioned thresholds and AI prompt, and tag records with the version that produced them.

The first version is seeded from config/thresholds.yaml when the app starts
(app.modules.model_config.service.ensure_seed_version), not here, so the default prompt text
lives in one place.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TAGGED = ("assessments", "recovery_plans", "reevaluation_decisions", "ai_output_logs")


def upgrade() -> None:
    op.create_table(
        "model_config_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("thresholds", sa.JSON(), nullable=False),
        sa.Column("prompt_instructions", sa.Text(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("parent_version", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_model_config_one_active", "model_config_versions", ["is_active"], unique=True,
        postgresql_where=sa.text("is_active"), sqlite_where=sa.text("is_active"),
    )
    for table in TAGGED:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("config_version_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                f"fk_{table}_config_version", "model_config_versions",
                ["config_version_id"], ["id"], ondelete="SET NULL",
            )
            batch.create_index(f"ix_{table}_config_version_id", ["config_version_id"])


def downgrade() -> None:
    for table in TAGGED:
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_config_version_id")
            batch.drop_constraint(f"fk_{table}_config_version", type_="foreignkey")
            batch.drop_column("config_version_id")
    op.drop_index("uq_model_config_one_active", table_name="model_config_versions")
    op.drop_table("model_config_versions")
