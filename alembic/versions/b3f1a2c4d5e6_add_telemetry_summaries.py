"""add telemetry_summaries

Revision ID: b3f1a2c4d5e6
Revises: 0c149baba2ad
Create Date: 2026-08-09 09:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "b3f1a2c4d5e6"
down_revision: str | None = "0c149baba2ad"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "telemetry_summaries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_key", sa.Integer(), nullable=False),
        sa.Column("driver_number", sa.Integer(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("max_speed", sa.Integer(), nullable=True),
        sa.Column("avg_speed", sa.Float(), nullable=True),
        sa.Column("max_rpm", sa.Integer(), nullable=True),
        sa.Column("max_gear", sa.Integer(), nullable=True),
        sa.Column("avg_throttle", sa.Float(), nullable=True),
        sa.Column("full_throttle_fraction", sa.Float(), nullable=True),
        sa.Column("brake_fraction", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_key", "driver_number", name="uq_telem_summary_session_driver"
        ),
    )
    op.create_index(
        "ix_telem_summary_session", "telemetry_summaries", ["session_key"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_telem_summary_session", table_name="telemetry_summaries")
    op.drop_table("telemetry_summaries")
