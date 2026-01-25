"""Initial schema with pgvector support

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("vendor_id", sa.String(length=255), nullable=False),
        sa.Column("doc_id", sa.String(length=255), nullable=False),
        sa.Column("doc_type", sa.String(length=50), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vendor_id", "doc_id", "chunk_index", name="uq_document_chunks"),
    )
    op.create_index("idx_document_chunks_vendor_doc", "document_chunks", ["vendor_id", "doc_id"])
    op.create_index("idx_document_chunks_metadata", "document_chunks", ["metadata"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("idx_document_chunks_metadata", table_name="document_chunks")
    op.drop_index("idx_document_chunks_vendor_doc", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.execute("DROP EXTENSION IF EXISTS vector")
