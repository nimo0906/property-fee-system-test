"""add SaaS payment receipt numbers

Revision ID: 0006_saas_payment_receipts
Revises: 0005_saas_bill_review_status
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_saas_payment_receipts"
down_revision = "0005_saas_bill_review_status"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payments", sa.Column("receipt_number", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("payments", "receipt_number")
