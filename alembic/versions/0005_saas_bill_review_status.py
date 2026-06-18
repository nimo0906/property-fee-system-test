"""set SaaS bills pending review by default

Revision ID: 0005_saas_bill_review_status
Revises: 0004_saas_ops_audit_tables
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_saas_bill_review_status"
down_revision = "0004_saas_ops_audit_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "bills",
        "status",
        existing_type=sa.Text(),
        server_default="pending_review",
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        "bills",
        "status",
        existing_type=sa.Text(),
        server_default="unpaid",
        existing_nullable=False,
    )
