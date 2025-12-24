"""add change_summaries cache table

Revision ID: 0002_change_summaries
Revises: 0001_initial
Create Date: 2025-12-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_change_summaries"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "change_summaries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("date_prev_id", sa.BigInteger(), sa.ForeignKey("dates.id"), nullable=False),
        sa.Column("date_curr_id", sa.BigInteger(), sa.ForeignKey("dates.id"), nullable=False),
        sa.Column("clazz", sa.Enum("occupied", "gray", "frontline", name="layer_class"), nullable=False),
        sa.Column("gained_km2", sa.Float(), nullable=False, server_default="0"),
        sa.Column("lost_km2", sa.Float(), nullable=False, server_default="0"),
        sa.Column("top_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("date_prev_id", "date_curr_id", "clazz", name="uk_change_summary_pair_class"),
    )
    op.create_index(
        "idx_change_summaries_curr_class",
        "change_summaries",
        ["date_curr_id", "clazz"],
    )


def downgrade() -> None:
    op.drop_index("idx_change_summaries_curr_class", table_name="change_summaries")
    op.drop_table("change_summaries")
