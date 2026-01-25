"""Add debug trace table

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "debug_traces",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("request_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("vendor_id", sa.String(length=255), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_debug_traces_request_id", "debug_traces", ["request_id"])
    op.create_index("idx_debug_traces_vendor_id", "debug_traces", ["vendor_id"])
    op.create_index("idx_debug_traces_created_at", "debug_traces", ["created_at"])
    op.create_index("idx_debug_traces_payload", "debug_traces", ["payload"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("idx_debug_traces_payload", table_name="debug_traces")
    op.drop_index("idx_debug_traces_created_at", table_name="debug_traces")
    op.drop_index("idx_debug_traces_vendor_id", table_name="debug_traces")
    op.drop_index("idx_debug_traces_request_id", table_name="debug_traces")
    op.drop_table("debug_traces")
