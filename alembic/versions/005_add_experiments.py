"""Add A/B testing experiment tracking tables

Revision ID: 005
Revises: 004
Create Date: 2024-01-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("traffic_split", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "experiment_variants",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("experiment_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("traffic_percentage", sa.Float(), nullable=False),
        sa.Column("is_control", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id", "name"),
    )

    op.create_table(
        "experiment_assignments",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("experiment_id", sa.BigInteger(), nullable=False),
        sa.Column("variant_id", sa.BigInteger(), nullable=False),
        sa.Column("request_id", sa.String(length=255), nullable=False),
        sa.Column("vendor_id", sa.String(length=255), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["experiment_variants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "experiment_metrics",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("experiment_id", sa.BigInteger(), nullable=False),
        sa.Column("variant_id", sa.BigInteger(), nullable=False),
        sa.Column("request_id", sa.String(length=255), nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["experiment_variants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_experiments_status", "experiments", ["status"])
    op.create_index("idx_experiment_assignments_request", "experiment_assignments", ["request_id"])
    op.create_index("idx_experiment_metrics_variant", "experiment_metrics", ["variant_id", "metric_name"])


def downgrade() -> None:
    op.drop_index("idx_experiment_metrics_variant", table_name="experiment_metrics")
    op.drop_index("idx_experiment_assignments_request", table_name="experiment_assignments")
    op.drop_index("idx_experiments_status", table_name="experiments")
    op.drop_table("experiment_metrics")
    op.drop_table("experiment_assignments")
    op.drop_table("experiment_variants")
    op.drop_table("experiments")
