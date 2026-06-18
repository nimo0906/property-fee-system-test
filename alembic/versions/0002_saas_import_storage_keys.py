"""add SaaS import storage metadata

Revision ID: 0002_saas_import_storage_keys
Revises: 0001_saas_baseline
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_saas_import_storage_keys"
down_revision = "0001_saas_baseline"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("imports", sa.Column("original_name", sa.Text(), nullable=True))
    op.add_column("imports", sa.Column("storage_key", sa.Text(), nullable=True))
    op.add_column("imports", sa.Column("file_size", sa.BigInteger(), nullable=True))
    op.add_column("imports", sa.Column("content_type", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("imports", "content_type")
    op.drop_column("imports", "file_size")
    op.drop_column("imports", "storage_key")
    op.drop_column("imports", "original_name")
